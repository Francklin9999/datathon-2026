"""Wire primitives. Optional keys differ from required, nullable fields."""

from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
)
from pydantic.alias_generators import to_camel
from typing_extensions import TypeAliasType


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="ignore",
        allow_inf_nan=False,
    )

    def to_wire(self) -> dict:
        """Preserve supplied optional nulls; omit keys that were never supplied."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


String = StrictStr
Boolean = StrictBool


def normalize_integer(value):
    # JSON Schema's integer includes 1.0 and 1e0. JavaScript cannot distinguish
    # those from 1, so accept integral numbers while rejecting booleans/strings.
    return int(value) if type(value) is float and value.is_integer() else value


Integer = Annotated[StrictInt, BeforeValidator(normalize_integer)]
Number = Annotated[float, Field(strict=True)]
NonNegative = Annotated[Number, Field(ge=0)]
Count = Annotated[Integer, Field(ge=0)]
Percent = Annotated[Number, Field(ge=0, le=100)]


def valid_date(value: str) -> str:
    date.fromisoformat(value)
    return value


def valid_timestamp(value: str) -> str:
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


ISODate = TypeAliasType(
    "ISODate",
    Annotated[
        String,
        Field(pattern=r"^\d{4}-\d{2}-\d{2}$", json_schema_extra={"format": "date"}),
        AfterValidator(valid_date),
    ],
)
ISODateTime = TypeAliasType(
    "ISODateTime",
    Annotated[
        String,
        Field(
            pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$",
            json_schema_extra={"format": "date-time"},
        ),
        AfterValidator(valid_timestamp),
    ],
)
ProfileId = TypeAliasType(
    "ProfileId",
    Annotated[String, Field(pattern=r"^(robert|amira|mateo|p_[0-9a-hjkmnp-tv-z]{10})$")],
)
SessionId = TypeAliasType(
    "SessionId",
    Annotated[
        String,
        Field(pattern=r"^s_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
    ],
)
RunId = TypeAliasType(
    "RunId", Annotated[String, Field(pattern=r"^run_[0-7][0-9A-HJKMNP-TV-Z]{25}$")]
)
FactId = TypeAliasType("FactId", Annotated[String, Field(pattern=r"^F-[0-9]{3,}$")])
EvidenceId = TypeAliasType("EvidenceId", Annotated[String, Field(pattern=r"^E-[0-9]{3,}$")])
FactKey = TypeAliasType(
    "FactKey", Annotated[String, Field(pattern=r"^[^|]+\|[^|:]+:[^|]+\|[^|]+\|[^|]+$")]
)
RuleCode = TypeAliasType("RuleCode", Annotated[String, Field(pattern=r"^R[1-9][0-9]*$")])
ScenarioId = TypeAliasType("ScenarioId", Annotated[String, Field(pattern=r"^sc_[a-z0-9_]+$")])
EventId = TypeAliasType("EventId", Annotated[String, Field(pattern=r"^evt_[0-9a-f]{12}$")])
DataVersion = TypeAliasType(
    "DataVersion", Annotated[String, Field(pattern=r"^snap-[0-9]{8}-[a-z0-9_-]+$")]
)
Ticker = TypeAliasType("Ticker", Annotated[String, Field(pattern=r"^[A-Z0-9][A-Z0-9.^=-]*$")])
