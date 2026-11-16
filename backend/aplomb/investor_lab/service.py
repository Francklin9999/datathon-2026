"""A deterministic Lab. Future prices and unverified disclosures never enter a checkpoint."""

from __future__ import annotations

import copy
import math
import secrets
from datetime import datetime, timezone

from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.api.storage import Write
from aplomb.contracts import api as a
from aplomb.contracts import investor_lab as l
from aplomb.contracts import models as m

CUTOFFS = ("2022-05-17", "2022-11-02", "2023-06-02")
TITLES = ("A broad decline", "When company evidence changes", "A growing concentration")
PROMPTS = (
    "Markets have fallen. Choose the weight you want in Company C, keeping your goal and cash needs in mind.",
    "The company has published new results. Decide which evidence would justify changing your position.",
    "Recent gains have changed your allocation. Decide how much concentration you intend to keep.",
)
TICKERS = ("SPY", "AGG", "MSFT", "CASH.USD", "GLD", "BTC-USD")
SLEEVES = ("Broad equities A", "Bond fund B", "Company C", "Cash reserve", "Gold D", "Crypto E")
RULE_LABELS = {
    "cap.position": "Maximum single-stock or crypto allocation",
    "cap.sector": "Maximum direct-equity sector allocation",
    "cap.growth_assets": "Maximum growth-asset allocation",
    "floor.fixed_income": "Minimum bonds and cash allocation",
    "limit.volatility": "Historical annualized volatility limit",
    "limit.stress_2022": "Historical stress-loss limit",
    "limit.drawdown": "Historical drawdown limit",
}
CONTRASTS = {
    "cash_need": "Suppose the same cash expense is fully covered outside this portfolio. With the same prices and company evidence, what would you do?",
    "company_evidence": "Suppose the price decline is identical, but the company evidence is unchanged from your original thesis. What would you do?",
    "loss_discomfort": "Suppose Company C rises by the same percentage instead, with unchanged business evidence. Would you keep the same concentration?",
    "portfolio_balance": "Suppose all other holdings also moved and Company C remained at its original portfolio weight. What would you do?",
    "long_term": "Suppose the goal moves to twelve months from now while the market and company evidence stay the same. What would you do?",
    "other": "Suppose no cash is needed for five years and the company evidence is unchanged. Which part of your decision would change?",
}
MACRO = (
    "Canada's central bank raised its policy rate to 1% and reported inflation of 5.7%.",
    "Canada's central bank raised its policy rate to 3.75%; inflation had eased to 6.9% but remained broad-based.",
    "Canada's central bank held its policy rate at 4.5% and reported that inflation had eased to 5.2%.",
)
LIMITATIONS = [
    "Educational simulation. Choices are assessed by your explanation and consistency, never by subsequent returns.",
    "Historical prices are retrospectively adjusted in the pinned sample; revisions and the selected universe can introduce hindsight.",
    "The chart is an indexed USD proxy illustration, not the historical performance of your actual holdings. Trades rebalance the other sleeves proportionally, with no fees or taxes.",
    "Company identities and calendar dates are masked until review. Original source links then reveal both.",
    "13F captures without verified historical availability are withheld from decisions. Disclosed holdings do not describe a manager's complete strategy.",
]


def invalid(message):
    return ServiceError("validation_error", message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def partition(session_id):
    return f"INVESTOR_LAB#{session_id}"


def redistribute(weights, target):
    """Target Company C; redistribute the remaining value proportionally."""
    rest = math.fsum(w for i, w in enumerate(weights) if i != 2)
    result = [w / rest * (100 - target) if i != 2 and rest else 0 for i, w in enumerate(weights)]
    result[2] = target
    if rest == 0:
        result[3] = 100 - target
    return result


def validate_action(decision, current):
    if decision.action == "hold" and abs(decision.target_pct - current) > 0.011:
        raise invalid("Hold must retain the current company weight")
    if decision.action == "buy" and decision.target_pct <= current + 0.001:
        raise invalid("Buy must increase the company weight")
    if decision.action == "sell" and decision.target_pct >= current - 0.001:
        raise invalid("Sell must reduce the company weight")


class InvestorLab:
    def __init__(self, store, profiles):
        self.store, self.profiles = store, profiles

    def _load(self, sid, lab_id):
        row = self.store.get("profiles", partition(sid), lab_id)
        if row is None:
            raise NotFound("This Investor Lab session is not available")
        return row

    def _save(self, sid, row, previous):
        row["revision"] = previous + 1
        self.store.transact([Write("profiles", partition(sid), row["labId"], row, previous)])
        return self.view(row)

    def _editable(self, sid, lab_id, version, stage):
        row = self._load(sid, lab_id)
        if row["revision"] != version:
            raise Conflict("This Lab changed. Reload it before continuing.")
        if row["stage"] != stage:
            raise Conflict("This action is not available at the current checkpoint")
        return row

    def list(self, sid):
        rows = self.store.query("profiles", partition(sid))
        return l.LabSessionsResponse(items=[self.view(row) for row in rows[-30:]])

    def get(self, sid, lab_id):
        return self.view(self._load(sid, lab_id))

    def _candidate(self, situation, base):
        context = copy.deepcopy(base.get("investorContext") or {}) if base else {}
        context.update(
            riskCapacity=situation.risk_capacity, riskCapacityOrigin="user",
            riskToleranceOrigin="user",
            liquidityNotes=(f"{situation.cash_need_pct:g}% of this fictional portfolio needed "
                            f"within {situation.cash_need_months} months."
                            if situation.cash_need_pct else "No planned withdrawal stated."),
        )
        preferences = copy.deepcopy(base["preferences"]) if base else {
            "themesOfInterest": [], "excludedSectors": [], "excludedAssetClasses": [],
            "esgFocus": False, "avoidControversies": False, "avoidSpeculative": False,
            "cryptoInterest": "none", "wantsDiversification": True, "notes": "",
        }
        portfolio = ({"totalValue": base["portfolio"]["totalValue"],
                      "positions": base["portfolio"]["positions"]} if base else None)
        if situation.holdings:
            portfolio = {"totalValue": situation.capital,
                         "positions": [p.to_wire() for p in situation.holdings]}
        if base and situation.reporting_currency != base["reportingCurrency"]:
            raise invalid("Keep the existing reporting currency when testing a profile")
        body = a.CreateProfileRequest(
            name=situation.name, age=base["age"] if base else None,
            risk_level=situation.risk_willingness,
            horizon_years=m.HorizonYears(min=situation.horizon_years, max=None),
            objective=situation.objective, experience=situation.experience,
            reporting_currency=situation.reporting_currency, preferences=preferences,
            investor_context=m.InvestorContext.model_validate(context),
            portfolio=portfolio, rules=None, from_draft_run_id=None,
        )
        pid = (base["profileId"] if base and not base["isDefault"] else
               "p_" + "".join(secrets.choice("0123456789abcdefghjkmnpqrstvwxyz") for _ in range(10)))
        stamp = now()
        candidate = self.profiles._custom_body(body, pid, stamp, created_at=stamp)
        if base is None and not situation.holdings:
            candidate["portfolio"]["totalValue"] = situation.capital
        candidate["version"] = 1
        return m.Profile.model_validate(candidate).to_wire()

    def start(self, sid, request):
        base = None
        if request.mode != "new":
            if not request.profile_id:
                raise invalid("Select the profile to test")
            profile = self.profiles.get(sid, request.profile_id)
            if request.profile_version != profile.version:
                raise Conflict("The profile changed. Reload before starting.")
            if profile.archived:
                raise invalid("Restore this profile before testing it")
            base = profile.to_wire()
        elif request.profile_id is not None:
            raise invalid("A new Lab does not take an existing profile")
        candidate = self._candidate(request.situation, base)
        snap = self.profiles.snapshot()
        # Read once into a private, pinned record. Only the active prefix is projected to the client.
        frame = snap.gate(CUTOFFS[-1], "historical").price_frame(
            list(TICKERS), start="2022-01-04", end=CUTOFFS[-1])
        prices = [{"date": day, "values": [frame.column(t)[i] for t in TICKERS]}
                  for i, day in enumerate(frame.dates)
                  if all(frame.column(t)[i] is not None for t in TICKERS)]
        if len(prices) < 100:
            raise ServiceError("insufficient_data", "The Lab needs the historical proxy price sample")
        weights = [50.0, 30.0, 10.0, 10.0, 0.0, 0.0]
        if base or request.situation.holdings:
            holdings = request.situation.holdings or [
                l.LabHolding.model_validate(p) for p in base["portfolio"]["positions"]]
            universe = snap.gate(snap.data_as_of).universe()
            largest = max((p for p in holdings
                           if universe.get(p.ticker).asset_class == "equity"),
                          key=lambda p: p.weight_pct, default=None)
            weights = [0.0] * len(TICKERS)
            for p in holdings:
                kind = universe.get(p.ticker).asset_class
                index = (2 if largest and p.ticker == largest.ticker else
                         {"equity": 0, "etf_equity": 0, "etf_bond": 1,
                          "cash": 3, "etf_commodity": 4, "crypto": 5}.get(kind, 0))
                weights[index] += p.weight_pct
            total = math.fsum(weights)
            weights = [w / total * 100 for w in weights]
        selected = [0, 1, 2]
        if request.mode == "quick":
            cap = next((r["threshold"] for r in base["rules"]
                        if r["ruleId"] == "cap.position" and r["enabled"]
                        and r["threshold"] is not None), 100)
            selected = [0 if request.situation.cash_need_pct else 2 if weights[2] > cap else 1]
        row = {
            "revision": 1, "labId": "lab_" + secrets.token_hex(12), "stage": "initial",
            "mode": request.mode, "profileId": request.profile_id, "base": base,
            "candidate": candidate, "situation": request.situation.to_wire(),
            "selected": selected, "index": 0, "observations": [], "weights": weights,
            "prices": prices, "dataVersion": snap.data_version, "createdAt": now(),
            "savedProfileId": None,
        }
        self.store.transact([Write("profiles", partition(sid), row["labId"], row, None)])
        return self.view(row)

    def _market(self, row):
        index = row["selected"][row["index"]]
        prices = [p for p in row["prices"] if p["date"] < CUTOFFS[index]]
        weights = row["weights"][:]
        units = [w / prices[0]["values"][i] for i, w in enumerate(weights)]
        decisions = {CUTOFFS[o["scenario"]]: o["final"]["targetPct"]
                     for o in row["observations"] if o.get("final")}
        chart = []
        for step, p in enumerate(prices):
            values = [units[i] * v for i, v in enumerate(p["values"])]
            value = math.fsum(values)
            weights = [v / value * 100 for v in values]
            chart.append({"step": step, "value": round(value, 4)})
            # The decision occurs after the last observation before the cutoff.
            next_day = prices[step + 1]["date"] if step + 1 < len(prices) else "9999"
            for cutoff, target in decisions.items():
                if p["date"] < cutoff <= next_day:
                    weights = redistribute(weights, target)
                    units = [value * w / 100 / p["values"][i] for i, w in enumerate(weights)]
        return chart, [round(w, 6) for w in weights]

    def _evidence(self, row):
        scenario = row["selected"][row["index"]]
        chart, weights = self._market(row)
        change = chart[-1]["value"] - chart[0]["value"]
        evidence = [
            dict(evidenceId="exposures", category="exposures", title="Look inside the allocation",
                 available=True, relativeDate="At this checkpoint",
                 summary=f"Company C is {weights[2]:.1f}% of the hypothetical portfolio. Bonds are {weights[1]:.1f}% and cash is {weights[3]:.1f}%. Increasing Company C reduces all other sleeves proportionally."),
            dict(evidenceId="macro", category="macro", title="The wider market",
                 available=True, relativeDate="Observed by this checkpoint",
                 summary=(f"{MACRO[scenario]} The indexed proxy portfolio changed {change:+.1f}% "
                          "since the starting observation. These facts do not establish why prices moved.")),
            dict(evidenceId="disclosure", category="disclosure", title="Institutional disclosures",
                 available=False, relativeDate="Historical availability not verified",
                 summary="The available 13F transcriptions cannot be verified as available at this checkpoint. They are withheld. You can compare dated holdings after the Lab."),
        ]
        if scenario >= 1:
            evidence.append(dict(
                evidenceId="company", category="company", title="Company C's published results",
                available=True, relativeDate="Published before this checkpoint",
                summary=("For its latest reported quarter, revenue rose 11% year over year, "
                         "operating income rose 6%, and net income fell 14%. "
                         "Revenue growth and profit growth point in different directions. "
                         "These figures alone do not establish whether the investment thesis is broken.")
                if scenario == 1 else (
                    "For its latest reported quarter, revenue rose 7% year over year, operating "
                    "income rose 10%, and net income rose 9%. These are published results, "
                    "not a forecast or a justification for any position size."),
            ))
        else:
            evidence.append(dict(evidenceId="company", category="company",
                                 title="Company evidence", available=False,
                                 relativeDate="Not included in this checkpoint",
                                 summary="No verified company release is included at this checkpoint. A falling price alone does not establish a weakening business."))
        return evidence

    def initial(self, sid, lab_id, request):
        row = self._editable(sid, lab_id, request.version, "initial")
        _, weights = self._market(row)
        validate_action(request.decision, weights[2])
        scenario = row["selected"][row["index"]]
        row["observations"].append({
            "checkpoint": row["index"] + 1, "scenario": scenario, "title": TITLES[scenario],
            "startingPct": weights[2], "initial": request.decision.to_wire(),
            "consultations": [], "final": None, "contrast": None,
            "revisitTrigger": "", "contrastPrompt": "", "interpretation": "",
        })
        row["stage"] = "research"
        return self._save(sid, row, request.version)

    def consult(self, sid, lab_id, request):
        row = self._editable(sid, lab_id, request.version, "research")
        item = next((e for e in self._evidence(row) if e["evidenceId"] == request.evidence_id), None)
        if item is None or not item["available"]:
            raise invalid("This evidence is unavailable at the simulated checkpoint")
        if len(request.why.strip()) < 5:
            raise invalid("Describe why this evidence matters to the decision")
        obs = row["observations"][-1]
        obs["consultations"] = [c for c in obs["consultations"]
                               if c["evidenceId"] != request.evidence_id]
        obs["consultations"].append({
            "evidenceId": request.evidence_id, "title": item["title"],
            "why": request.why.strip(), "consultedAt": now(),
        })
        return self._save(sid, row, request.version)

    def final(self, sid, lab_id, request):
        row = self._editable(sid, lab_id, request.version, "research")
        obs = row["observations"][-1]
        validate_action(request.decision, obs["startingPct"])
        if len(request.revisit_trigger.strip()) < 10:
            raise invalid("Describe what would make you revisit the decision")
        obs["final"] = request.decision.to_wire()
        obs["revisitTrigger"] = request.revisit_trigger.strip()
        obs["contrastPrompt"] = CONTRASTS[request.decision.reason]
        row["stage"] = "contrast"
        return self._save(sid, row, request.version)

    def contrast(self, sid, lab_id, request):
        row = self._editable(sid, lab_id, request.version, "contrast")
        obs = row["observations"][-1]
        validate_action(request.decision, obs["startingPct"])
        obs["contrast"] = request.decision.to_wire()
        changed = abs(request.decision.target_pct - obs["final"]["targetPct"]) > 0.01
        obs["interpretation"] = (
            "Your position size changed when the stated circumstance changed. Confirm which condition matters in your playbook."
            if changed else
            "Your position size stayed the same in the contrast. This alone cannot distinguish conviction, cash needs, and loss tolerance."
        )
        if row["index"] + 1 < len(row["selected"]):
            row["index"] += 1
            row["stage"] = "initial"
        else:
            row["stage"] = "review"
        return self._save(sid, row, request.version)

    def _settings(self, row):
        base, candidate = row["base"], row["candidate"]
        current = base or {}
        proposals = []
        fields = [
            ("name", "Profile name"), ("objective", "Investment goal"),
            ("horizonYears", "Investment horizon"), ("experience", "Experience"),
            ("riskLevel", "Willingness to take risk"),
            ("reportingCurrency", "Reporting currency"),
        ]

        def display(value):
            return f'{value["min"]:g} years or more' if isinstance(value, dict) else str(value)

        for key, label in fields:
            before, after = current.get(key), candidate[key]
            if before != after:
                proposals.append(dict(key=key, label=label,
                                      current=display(before) if before is not None else None,
                                      proposed=display(after), basis=["Stated circumstances"],
                                      explanation="Explicitly stated before the exercise.", required=base is None))
        if base is None:
            portfolio = candidate["portfolio"]
            allocation = ", ".join(f'{p["ticker"]} {p["weightPct"]:g}%'
                                   for p in portfolio["positions"])
            supplied = bool(row["situation"]["holdings"])
            proposals.append(dict(
                key="portfolio", label="Fictional starting portfolio", current=None,
                proposed=f'{portfolio["currency"]} {portfolio["totalValue"]:,.0f} · {allocation}',
                basis=["Optional holdings supplied" if supplied else "Stated circumstances"],
                explanation=("The holdings you supplied for the saved profile." if supplied else
                             "Aplomb's proposed starting allocation for the saved profile. "
                             "The masked exercise used its separate historical proxy basket."),
                required=True,
            ))
        old_context = current.get("investorContext") or {}
        for key, label in (("riskCapacity", "Financial capacity for risk"), ("liquidityNotes", "Planned cash needs")):
            after = candidate["investorContext"][key]
            if old_context.get(key) != after:
                proposals.append(dict(key=f"context.{key}", label=label, current=old_context.get(key),
                                      proposed=after, basis=["Stated circumstances"],
                                      explanation="Capacity and cash needs remain separate from observed willingness.", required=base is None))
        existing = {r["ruleId"]: r for r in current.get("rules", [])}
        observations = row["observations"]
        for rule in candidate["rules"]:
            old = existing.get(rule["ruleId"])
            if old is not None and old["threshold"] == rule["threshold"] and rule["ruleId"] != "cap.position":
                continue
            if old is not None and (not rule["editable"] or rule["threshold"] is None):
                continue
            concentration = rule["ruleId"] == "cap.position"
            value = old["threshold"] if old is not None and concentration else rule["threshold"]
            proposals.append(dict(
                key=f'rule.{rule["ruleId"]}',
                label=RULE_LABELS.get(rule["ruleId"], rule["label"]["en"]),
                current=(f'{old["threshold"]:g}%' if old and old["threshold"] is not None else "Enabled" if old else None),
                proposed=f"{value:g}%" if value is not None else "Enabled",
                value=value, minimum=rule["bounds"]["min"] if rule["bounds"] else None,
                maximum=rule["bounds"]["max"] if rule["bounds"] else None,
                basis=([f'Checkpoint {o["checkpoint"]}: {o["title"]}' for o in observations] if concentration else ["Stated circumstances", "Existing Aplomb rule derivation"]),
                explanation=("Choose the intended limit. A simulated position size is an observation, not a risk recommendation."
                             if concentration else rule["rationale"]["en"]),
                required=base is None,
            ))
        return proposals

    def view(self, row):
        reviewing = row["stage"] in ("review", "saved")
        scenario = row["selected"][row["index"]]
        chart, weights = self._market(row)
        evidence = self._evidence(row) if row["stage"] == "research" else []
        # Titles are discoverable; evidence content unlocks only after the initial choice.
        observations = [l.LabObservation.model_validate(o) for o in row["observations"]]
        last = observations[-1] if observations else None
        prompt = (last.contrast_prompt if row["stage"] == "contrast" and last else PROMPTS[scenario])
        if row["index"] and row["stage"] == "initial":
            prompt += " Reconsider the explanation you gave at the previous checkpoint."
        return l.LabSession(
            lab_id=row["labId"], version=row["revision"], mode=row["mode"], stage=row["stage"],
            profile_id=row["profileId"], saved_profile_id=row["savedProfileId"],
            situation=l.LabSituation.model_validate(row["situation"]),
            checkpoint=row["index"] + 1, checkpoint_count=len(row["selected"]),
            title=TITLES[scenario], prompt=prompt, chart=chart,
            sleeves=[l.LabSleeve(label=label, weight_pct=w) for label, w in zip(SLEEVES, weights)],
            focus_pct=weights[2], evidence=evidence, observations=observations,
            settings=self._settings(row) if reviewing else [],
            proposed_principle=("Size positions against a confirmed concentration limit; explain changes using cash needs, allocation, and company evidence separately."),
            proposed_revisit_trigger=last.revisit_trigger if last else "",
            limitations=LIMITATIONS,
            reveal=([
                f'Checkpoint {i + 1}: information cutoff {CUTOFFS[s]}. Dates and identities were masked during decisions.'
                for i, s in enumerate(row["selected"])
            ] + [
                "Proxies: A = SPY, B = AGG, C = Microsoft, D = GLD, E = BTC-USD. Present-day holdings were mapped to these illustrative sleeves.",
                "Company evidence: Microsoft FY2023 Q1, published 2022-10-25; FY2023 Q3, published 2023-04-25.",
                "https://www.microsoft.com/en-us/Investor/earnings/FY-2023-Q1/press-release-webcast",
                "https://www.microsoft.com/en-us/Investor/earnings/FY-2023-Q3/press-release-webcast",
                "Canadian policy statements: https://www.bankofcanada.ca/2022/04/fad-press-release-2022-04-13/ ; https://www.bankofcanada.ca/2022/10/fad-press-release-2022-10-26/ ; https://www.bankofcanada.ca/2023/04/fad-press-release-2023-04-12/",
                f'Price snapshot: {row["dataVersion"]}. No subsequent return is used to score a decision.',
            ] if reviewing else []),
        )

    def confirm(self, sid, lab_id, request):
        row = self._load(sid, lab_id)
        if row["stage"] == "saved":
            return self.profiles.get(sid, row["savedProfileId"])
        row = self._editable(sid, lab_id, request.version, "review")
        if any(len(v.strip()) < 10 for v in (request.principle, request.revisit_trigger, request.explanation)):
            raise invalid("Explain the playbook, revisit trigger, and confirmation")
        proposals = {p["key"]: p for p in self._settings(row)}
        accepted = {p.key: p for p in request.accepted}
        if len(accepted) != len(request.accepted) or set(accepted) - set(proposals):
            raise invalid("Accept only distinct proposed settings")
        if any(p.get("required") and key not in accepted for key, p in proposals.items()):
            raise invalid("Confirm each proposed setting before creating the profile")
        base, candidate = row["base"], row["candidate"]
        if base:
            current, stored = self.profiles._load(sid, base["profileId"])
            if current.version != base["version"]:
                raise Conflict("Your profile changed during this Lab. Start a new check to review against the latest settings.")
            data = copy.deepcopy(base)
            if base["isDefault"]:
                data.update(profileId=candidate["profileId"], isDefault=False, origin="user", version=1,
                            createdAt=now(), name=candidate["name"])
        else:
            data, stored = copy.deepcopy(candidate), None
        context = data.setdefault("investorContext", {})
        if context is None:
            context = data["investorContext"] = {}
        changes = []
        for key, selected in accepted.items():
            proposal = proposals[key]
            after = proposal["proposed"]
            if key.startswith("rule."):
                rid = key.removeprefix("rule.")
                rule = copy.deepcopy(next(r for r in candidate["rules"] if r["ruleId"] == rid))
                if rule["threshold"] is not None:
                    value = selected.value if selected.value is not None else proposal["value"]
                    if not rule["editable"] and value != rule["threshold"]:
                        raise invalid(f"{proposal['label']} cannot be edited")
                    minimum, maximum = proposal["minimum"], proposal["maximum"]
                    if (not math.isfinite(value)
                            or (minimum is not None and value < minimum)
                            or (maximum is not None and value > maximum)):
                        raise invalid(f"Choose a value within the displayed bounds for {proposal['label']}")
                    if rule["editable"]:
                        rule.update(threshold=value, origin="user", derivation=None, updatedAt=now())
                    after = f"{value:g}%"
                elif selected.value is not None:
                    raise invalid(f"{proposal['label']} does not have a threshold")
                data["rules"] = [rule if r["ruleId"] == rid else r for r in data["rules"]]
                if not any(r["ruleId"] == rid for r in data["rules"]):
                    data["rules"].append(rule)
            elif key.startswith("context."):
                if selected.value is not None:
                    raise invalid("Only threshold settings take a numeric value")
                field = key.removeprefix("context.")
                context[field] = candidate["investorContext"][field]
                if field == "riskCapacity":
                    context["riskCapacityOrigin"] = "user"
            else:
                if selected.value is not None:
                    raise invalid("Only threshold settings take a numeric value")
                data[key] = candidate[key]
                if key == "name":
                    data["initial"] = candidate["initial"]
                if key == "objective":
                    data["objectiveText"] = candidate["objectiveText"]
                if key == "riskLevel":
                    context["riskToleranceOrigin"] = "user"
                context.setdefault("inputOrigins", {})[key] = "user"
            changes.append(l.LabSettingChange(key=key, label=proposal["label"],
                                             before=proposal["current"], after=after,
                                             basis=proposal["basis"]).to_wire())
        # Confirmation, not a simulated choice, is the only write to a profile.
        history = copy.deepcopy((context.get("playbook") or {}).get("reviews", []))[-29:]
        stamp = now()
        history.append(l.LabReviewRecord(
            lab_id=lab_id, confirmed_at=stamp, mode=row["mode"], explanation=request.explanation.strip(),
            situation=l.LabSituation.model_validate(row["situation"]),
            observations=[l.LabObservation.model_validate(o) for o in row["observations"]],
            changes=changes,
        ).to_wire())
        context["playbook"] = l.InvestmentPlaybook(
            principle=request.principle.strip(), revisit_trigger=request.revisit_trigger.strip(),
            interest=row["situation"]["interest"], updated_at=stamp, reviews=history,
        ).to_wire()
        data["updatedAt"] = stamp
        is_update = bool(base and not base["isDefault"])
        revision = stored["revision"] if is_update else None
        data["version"] = revision + 1 if revision else 1
        # Keep policy labels and codes canonical when an optional rule was added.
        from aplomb.profiles.rulebuilder import renumber
        data["rules"] = renumber(data["rules"])
        profile = m.Profile.model_validate(data)
        row.update(stage="saved", savedProfileId=profile.profile_id, revision=request.version + 1)
        value = {"revision": profile.version, "value": profile.to_wire(),
                 "profileId": profile.profile_id, "overlay": False}
        writes = [
            Write("profiles", f"SESSION#{sid}", f"PROFILE#{profile.profile_id}", value, revision),
            Write("profiles", partition(sid), lab_id, row, request.version),
        ]
        if base and base["isDefault"]:
            # Fence the source overlay too, so a concurrent edit cannot invalidate the copy.
            writes.append(Write("profiles", f"SESSION#{sid}", f'OVERLAY#{base["profileId"]}',
                                stored, stored["revision"] if stored else None))
        self.store.transact(writes)
        return profile

    def edit_playbook(self, sid, profile_id, request):
        profile, stored = self.profiles._load(sid, profile_id)
        if profile.is_default:
            raise invalid("Complete a Lab to save a personal copy of this example")
        if profile.version != request.version:
            raise Conflict()
        context = profile.investor_context
        if context is None or context.playbook is None:
            raise invalid("Complete an Investor Lab before editing its playbook")
        if any(len(s.strip()) < 10 for s in (request.principle, request.revisit_trigger, request.explanation)):
            raise invalid("Explain the change in at least ten characters")
        data = profile.to_wire()
        playbook = data["investorContext"]["playbook"]
        stamp = now()
        previous = playbook["reviews"][-1]
        changes = [
            dict(key=key, label=label, before=playbook[key], after=value,
                 basis=["Explicit playbook edit"])
            for key, label, value in [
                ("principle", "Decision principle", request.principle.strip()),
                ("revisitTrigger", "Revisit trigger", request.revisit_trigger.strip())]
            if playbook[key] != value
        ]
        playbook.update(principle=request.principle.strip(), revisitTrigger=request.revisit_trigger.strip(),
                        updatedAt=stamp, reviews=[*playbook["reviews"][-29:], {
                            **previous, "labId": "edit_" + secrets.token_hex(8),
                            "confirmedAt": stamp, "explanation": request.explanation.strip(),
                            "observations": [], "changes": changes,
                        }])
        data["updatedAt"] = stamp
        return self.profiles._save(sid, m.Profile.model_validate(data), stored)
