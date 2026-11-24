import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://gymos:gymos@localhost:5432/gymos_test")
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_admin, seed_catalog  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as c:
        c.execute(text("TRUNCATE " + ", ".join(t.name for t in Base.metadata.sorted_tables) + " RESTART IDENTITY CASCADE"))
    with SessionLocal() as s:
        seed_catalog(s)
        seed_admin(s, "admin@manima.co.in", "AdminPass123")
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


class Api:
    def __init__(self, client: TestClient):
        self.c = client
        self.token: str | None = None
        self.org_id: int | None = None

    def _h(self, extra=None):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.org_id:
            h["X-Org-Id"] = str(self.org_id)
        return {**h, **(extra or {})}

    def get(self, path, **kw):
        return self.c.get(API + path, headers=self._h(kw.pop("headers", None)), **kw)

    def post(self, path, json=None, **kw):
        return self.c.post(API + path, json=json, headers=self._h(kw.pop("headers", None)), **kw)

    def patch(self, path, json=None, **kw):
        return self.c.patch(API + path, json=json, headers=self._h(kw.pop("headers", None)), **kw)

    def put(self, path, json=None, **kw):
        return self.c.put(API + path, json=json, headers=self._h(kw.pop("headers", None)), **kw)

    def login(self, login, password):
        r = self.c.post(API + "/auth/login", json={"login": login, "password": password})
        assert r.status_code == 200, r.text
        self.token = r.json()["access_token"]
        return self


@pytest.fixture
def client():
    return TestClient(app)


def new_api(client) -> Api:
    return Api(client)


def signup(client, gym="Power Fit", email="owner@pf.in", phone="9000000001", plan="basic", area="Kukatpally"):
    r = client.post(API + "/public/signup", json={
        "gym_name": gym, "owner_name": "Ravi Kumar", "email": email, "phone": phone, "password": "OwnerPass123",
        "plan_code": plan, "area": area})
    assert r.status_code == 201, r.text
    api = Api(client).login(email, "OwnerPass123")
    api.org_id = r.json()["org_id"]
    return api


@pytest.fixture
def admin(client):
    return Api(client).login("admin@manima.co.in", "AdminPass123")
