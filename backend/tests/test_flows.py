from datetime import date, timedelta

from conftest import Api, signup

from app.jobs.daily import run_all
from app.models import Notification, Organization


def _member(api: Api, phone="9888800001", name="Anil Reddy", **kw):
    r = api.post("/members", {"full_name": name, "phone": phone, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _plan(api: Api, days=30, price=1500, **kw):
    r = api.post("/membership-plans", {"name": f"{days}d", "duration_days": days, "price": price, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_signup_me_and_dashboard(client):
    owner = signup(client)
    me = owner.get("/auth/me").json()
    assert me["staff_of"][0]["role"] == "owner" and me["staff_of"][0]["plan"] == "basic"
    assert "attendance_qr" in me["staff_of"][0]["features"]
    branches = owner.get("/branches").json()
    assert len(branches) == 1 and branches[0]["area"] == "Kukatpally"
    assert owner.get("/dashboard").status_code == 200


def test_member_subscription_payment_and_invoice(client):
    owner = signup(client)
    m = _member(owner)
    plan = _plan(owner)
    r = owner.post(f"/members/{m['id']}/subscriptions",
                   {"plan_id": plan["id"], "discount": 100, "payment": {"amount": 1000, "method": "upi"}})
    assert r.status_code == 201, r.text
    sub = r.json()["subscription"]
    assert sub["amount_due"] == 400 and sub["days_left"] == 29
    r = owner.post(f"/subscriptions/{sub['id']}/payments", {"amount": 500, "method": "cash"})
    assert r.status_code == 400  # overpay rejected
    r = owner.post(f"/subscriptions/{sub['id']}/payments", {"amount": 400, "method": "cash"})
    assert r.status_code == 201 and r.json()["invoice_no"].endswith("00002")
    # renewal starts after current end
    r = owner.post(f"/members/{m['id']}/subscriptions", {"plan_id": plan["id"]})
    assert r.json()["subscription"]["start_date"] == str(date.today() + timedelta(days=30))
    pays = owner.get("/payments").json()
    assert pays["count"] == 2 and pays["total_amount"] == 1400
    assert owner.get(f"/payments/{pays['items'][0]['id']}/receipt").status_code == 200
    assert owner.get("/members", params={"membership": "active"}).json()["total"] == 1


def test_tenant_isolation(client):
    a = signup(client)
    b = signup(client, gym="Iron Den", email="b@iron.in", phone="9000000002")
    m = _member(a)
    assert b.get(f"/members/{m['id']}").status_code == 404
    assert b.get("/members").json()["total"] == 0
    b.org_id = a.org_id  # pretend to be in another org
    assert b.get("/members").status_code == 403


def test_feature_gating_and_admin_override(client, admin):
    owner = signup(client)
    r = owner.get("/leads")
    assert r.status_code == 402 and r.json()["detail"]["code"] == "feature_not_in_plan"
    assert admin.put(f"/platform/tenants/{owner.org_id}/features/crm", {"enabled": True}).status_code == 200
    assert owner.get("/leads").status_code == 200
    # global kill switch beats overrides
    admin.patch("/platform/features/crm", {"enabled": False})
    assert owner.get("/leads").status_code == 402


def test_plan_limits(client, admin):
    owner = signup(client)
    r = owner.post("/branches", {"name": "Second", "area": "Miyapur"})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "limit_reached"
    admin.patch(f"/platform/tenants/{owner.org_id}", {"plan_code": "plus"})
    r = owner.post("/branches", {"name": "Second", "area": "Miyapur"})
    assert r.status_code == 201
    assert owner.get("/auth/me").json()["staff_of"][0]["type"] == "multi"


def test_qr_checkin_flow(client):
    owner = signup(client)
    branch = owner.get("/branches").json()[0]
    assert owner.get(f"/branches/{branch['id']}/qr-poster.png").headers["content-type"] == "image/png"
    landing = client.get(f"/api/v1/public/branches/{branch['code']}").json()
    assert landing["gym_name"] == "Power Fit" and landing["area"] == "Kukatpally"

    m = _member(owner, phone="9777700001")
    # member logs in with OTP
    otp = client.post("/api/v1/auth/otp/request", json={"phone": "+91 97777 00001"}).json()["dev_otp"]
    tok = client.post("/api/v1/auth/otp/verify", json={"phone": "9777700001", "code": otp}).json()["access_token"]
    member = Api(client)
    member.token = tok
    r = member.post("/me/checkin", {"branch_code": branch["code"]})
    assert r.status_code == 402  # no membership yet
    plan = _plan(owner)
    owner.post(f"/members/{m['id']}/subscriptions", {"plan_id": plan["id"]})
    r = member.post("/me/checkin", {"branch_code": branch["code"]})
    assert r.status_code == 200 and r.json()["duplicate"] is False
    assert member.post("/me/checkin", {"branch_code": branch["code"]}).json()["duplicate"] is True
    assert len(owner.get("/attendance").json()) == 1
    assert member.get("/me/gyms").json()[0]["gym"] == "Power Fit"


def test_rotating_qr_premium(client, admin):
    owner = signup(client, plan="premium")
    branch = owner.get("/branches").json()[0]
    m = _member(owner, phone="9777700002")
    owner.post(f"/members/{m['id']}/subscriptions", {"plan_id": _plan(owner)["id"]})
    otp = client.post("/api/v1/auth/otp/request", json={"phone": "9777700002"}).json()["dev_otp"]
    member = Api(client)
    member.token = client.post("/api/v1/auth/otp/verify", json={"phone": "9777700002", "code": otp}).json()["access_token"]
    assert member.post("/me/checkin", {"branch_code": branch["code"]}).status_code == 400
    live = owner.get(f"/branches/{branch['id']}/live-qr").json()
    assert member.post("/me/checkin", {"branch_code": branch["code"], "token": live["token"]}).status_code == 200


def test_rbac_front_desk(client):
    owner = signup(client, plan="plus")
    branch = owner.get("/branches").json()[0]
    r = owner.post("/staff", {"full_name": "Desk", "phone": "9666600001", "password": "DeskPass123",
                              "role": "front_desk", "branch_id": branch["id"]})
    assert r.status_code == 201, r.text
    desk = Api(client).login("9666600001", "DeskPass123")
    desk.org_id = owner.org_id
    assert desk.post("/members", {"full_name": "X Y", "phone": "9555500001"}).status_code == 201
    assert desk.get("/dashboard").status_code == 403  # no revenue view
    assert desk.post("/branches", {"name": "B", "area": "C"}).status_code == 403


def test_reminders_and_saas_lifecycle(client, admin, db):
    owner = signup(client, plan="plus")
    m = _member(owner, phone="9444400001", email="anil@x.in")
    plan = _plan(owner, days=8)  # ends in 7 days
    owner.post(f"/members/{m['id']}/subscriptions", {"plan_id": plan["id"]})
    stats = run_all(db, send_summary=True)
    assert stats["sent"] >= 1
    n = db.query(Notification).filter_by(template="renewal_due").one()
    assert n.channel == "sms" and n.status == "sent"
    run_all(db)  # idempotent: no duplicate reminder
    assert db.query(Notification).filter_by(template="renewal_due").count() == 1

    # trial expiry -> suspended -> owner blocked; payment reactivates
    org = db.get(Organization, owner.org_id)
    org.trial_ends_at = date.today() - timedelta(days=1)
    db.commit()
    run_all(db)
    assert owner.get("/members").status_code == 402
    r = admin.post(f"/platform/tenants/{owner.org_id}/payments", {"periods": 1})
    assert r.status_code == 201 and r.json()["status"] == "active"
    assert owner.get("/members").status_code == 200
    dash = admin.get("/platform/dashboard").json()
    assert dash["mrr"] == 2499 and dash["collected_this_month"] == 2499


def test_freeze_extends_membership(client, db):
    owner = signup(client, plan="plus")
    m = _member(owner)
    plan = _plan(owner, max_freeze_days=10)
    sub = owner.post(f"/members/{m['id']}/subscriptions", {"plan_id": plan["id"]}).json()["subscription"]
    assert owner.post(f"/subscriptions/{sub['id']}/freeze").json()["status"] == "frozen"
    from app.models import MemberSubscription
    s = db.get(MemberSubscription, sub["id"])
    s.frozen_from = date.today() - timedelta(days=4)
    db.commit()
    r = owner.post(f"/subscriptions/{sub['id']}/unfreeze").json()
    assert r["status"] == "active" and r["end_date"] == str(date.fromisoformat(sub["end_date"]) + timedelta(days=4))
