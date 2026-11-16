from typing import Annotated

from fastapi import APIRouter, Depends

from aplomb.api.errors import unavailable
from aplomb.contracts import investor_lab as l
from aplomb.contracts.models import Profile

from .service import InvestorLab


def investor_lab_router(store, profiles, session, feature):
    router = APIRouter(prefix="/v1")
    Session = Annotated[str, Depends(session)]

    def service():
        feature("profile_creator")
        if profiles is None or not hasattr(profiles, "snapshot"):
            raise unavailable("Investor Lab profile service")
        return InvestorLab(store, profiles)

    @router.get("/investor-lab", response_model=l.LabSessionsResponse)
    def sessions(sid: Session):
        return service().list(sid)

    @router.post("/investor-lab", response_model=l.LabSession, status_code=201)
    def start(body: l.LabStartRequest, sid: Session):
        return service().start(sid, body)

    @router.get("/investor-lab/{lab_id}", response_model=l.LabSession)
    def get(lab_id: str, sid: Session):
        return service().get(sid, lab_id)

    @router.post("/investor-lab/{lab_id}/initial", response_model=l.LabSession)
    def initial(lab_id: str, body: l.LabInitialRequest, sid: Session):
        return service().initial(sid, lab_id, body)

    @router.post("/investor-lab/{lab_id}/consult", response_model=l.LabSession)
    def consult(lab_id: str, body: l.LabConsultRequest, sid: Session):
        return service().consult(sid, lab_id, body)

    @router.post("/investor-lab/{lab_id}/final", response_model=l.LabSession)
    def final(lab_id: str, body: l.LabFinalRequest, sid: Session):
        return service().final(sid, lab_id, body)

    @router.post("/investor-lab/{lab_id}/contrast", response_model=l.LabSession)
    def contrast(lab_id: str, body: l.LabContrastRequest, sid: Session):
        return service().contrast(sid, lab_id, body)

    @router.post("/investor-lab/{lab_id}/confirm", response_model=Profile, response_model_exclude_unset=True)
    def confirm(lab_id: str, body: l.LabConfirmRequest, sid: Session):
        return service().confirm(sid, lab_id, body)

    @router.put("/profiles/{profile_id}/playbook", response_model=Profile, response_model_exclude_unset=True)
    def edit_playbook(profile_id: str, body: l.LabPlaybookRequest, sid: Session):
        return service().edit_playbook(sid, profile_id, body)

    return router
