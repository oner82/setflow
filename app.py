from __future__ import annotations
import os
import json
import sqlite3
import datetime as dt
from typing import Optional
from collections import defaultdict, OrderedDict

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text

from setflow.db import SessionLocal, DB_PATH
from setflow.models import (
    Base,
    Item,
    Department,
    Surgery,
    ProcedureDefault,
    UsageRecord,
    SetInstance,
    MachineConfig,
)
from setflow.db import ENGINE

APP_SECRET = os.environ.get("SETFLOW_SECRET", "setflow-dev-secret")
OR_PIN = os.environ.get("OR_PIN", "1234")
CSR_PIN = os.environ.get("CSR_PIN", "5678")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "0000")


def now():
    return dt.datetime.now(dt.timezone.utc)


def to_local(d: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if not d:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone(dt.timedelta(hours=9)))


def fmt_hm(d: Optional[dt.datetime]) -> str:
    ld = to_local(d)
    return ld.strftime("%H:%M") if ld else "-"


def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS machine_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_key VARCHAR(50) UNIQUE,
        machine_name VARCHAR(100),
        process_type VARCHAR(20),
        duration_minutes INTEGER,
        active BOOLEAN DEFAULT 1
    )
    """)

    cur.execute("PRAGMA table_info(usage_records)")
    cols = {row[1] for row in cur.fetchall()}
    wanted = {
        "csr_received_at": "ALTER TABLE usage_records ADD COLUMN csr_received_at DATETIME",
        "process_started_at": "ALTER TABLE usage_records ADD COLUMN process_started_at DATETIME",
        "process_due_at": "ALTER TABLE usage_records ADD COLUMN process_due_at DATETIME",
        "machine_key": "ALTER TABLE usage_records ADD COLUMN machine_key VARCHAR(50)",
        "machine_name": "ALTER TABLE usage_records ADD COLUMN machine_name VARCHAR(100)",
        "process_minutes": "ALTER TABLE usage_records ADD COLUMN process_minutes INTEGER",
        "release_requested_at": "ALTER TABLE usage_records ADD COLUMN release_requested_at DATETIME",
    }
    for col, sql in wanted.items():
        if col not in cols:
            cur.execute(sql)

    defaults = [
        ("handwash", "손세척", "wash", 10),
        ("washer1", "자동세척기 1호기", "wash", 30),
        ("washer2", "자동세척기 2호기", "wash", 30),
        ("steam1", "고압증기멸균기 1호기", "ster", 70),
        ("steam2", "고압증기멸균기 2호기", "ster", 73),
        ("steam3", "고압증기멸균기 3호기", "ster", 70),
        ("plasma1", "플라즈마 멸균기 1번", "ster", 50),
        ("plasma2", "플라즈마 멸균기 2번", "ster", 30),
        ("eo", "EO 멸균기", "ster", 900),
    ]
    for key, name, ptype, mins in defaults:
        cur.execute(
            "INSERT OR IGNORE INTO machine_configs (machine_key, machine_name, process_type, duration_minutes, active) VALUES (?,?,?,?,1)",
            (key, name, ptype, mins),
        )
    conn.commit()
    conn.close()
    Base.metadata.create_all(ENGINE)


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup_event():
    migrate_db()


def template_ctx(request: Request, active: str, label: str = ""):
    return {
        "request": request,
        "active": active,
        "role": request.session.get("role"),
        "label": label or request.session.get("label", ""),
    }


def require_role(request: Request, role: str):
    if request.session.get("role") != role:
        return False
    return True


def require_login(request: Request):
    return request.session.get("role") in {"or", "csr", "admin"}


def process_rank(status: str) -> int:
    order = {
        "반납": 1,
        "반입확인": 2,
        "세척중": 3,
        "세척완료": 4,
        "멸균중": 5,
        "멸균완료": 6,
        "불출": 7,
    }
    return order.get(status, 99)


@app.get("/")
def root(request: Request):
    role = request.session.get("role")
    if role == "or":
        return RedirectResponse("/or-use")
    if role == "csr":
        return RedirectResponse("/csr")
    if role == "admin":
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", template_ctx(request, active="login"))


@app.post("/login/or")
def login_or(request: Request, room_no: int = Form(...), pin: str = Form(...)):
    if pin != OR_PIN:
        return RedirectResponse("/login", status_code=302)
    request.session.clear()
    request.session["role"] = "or"
    request.session["room_no"] = room_no
    request.session["label"] = f"OR {room_no}번방"
    return RedirectResponse("/or-use", status_code=302)


@app.post("/login/csr")
def login_csr(request: Request, pin: str = Form(...)):
    if pin != CSR_PIN:
        return RedirectResponse("/login", status_code=302)
    request.session.clear()
    request.session["role"] = "csr"
    request.session["label"] = "CSR"
    return RedirectResponse("/csr", status_code=302)


@app.post("/login/admin")
def login_admin(request: Request, pin: str = Form(...)):
    if pin != ADMIN_PIN:
        return RedirectResponse("/login", status_code=302)
    request.session.clear()
    request.session["role"] = "admin"
    request.session["label"] = "관리자"
    return RedirectResponse("/admin", status_code=302)


@app.get("/logout")
@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/or-use", response_class=HTMLResponse)
def or_use_page(
    request: Request,
    db=Depends(db_dep),
    department_id: Optional[int] = None,
    surgery_id: Optional[str] = None,
    surgery_order: int = 1,
    is_contaminated: int = 0,
    manual_surgery_name: str = "",
):
    if request.session.get("role") != "or":
        return RedirectResponse("/login")

    room_no = request.session.get("room_no")
    surgery_id_int = int(surgery_id) if surgery_id not in (None, "") else None

    departments = db.query(Department).filter(Department.active == True).order_by(Department.name).all()
    surgeries = []
    defaults = []
    set_items = db.query(Item).filter(Item.active == True, Item.kind == "set").order_by(Item.name).all()
    single_items = db.query(Item).filter(Item.active == True, Item.kind == "instrument").order_by(Item.name).all()

    if department_id:
        surgeries = db.query(Surgery).filter(Surgery.department_id == department_id, Surgery.active == True).order_by(Surgery.name).all()
    if surgery_id_int:
        defaults = db.query(ProcedureDefault).filter(ProcedureDefault.surgery_id == surgery_id_int).all()

    set_instances = db.query(SetInstance).join(Item, SetInstance.set_item_id == Item.id).filter(
        SetInstance.active == True,
        Item.active == True,
        Item.kind == "set",
    ).order_by(Item.name, SetInstance.serial_no).all()
    set_instance_map: dict[int, list[dict]] = defaultdict(list)
    for si in set_instances:
        set_instance_map[si.set_item_id].append(
            {
                "id": si.id,
                "serial_no": si.serial_no,
                "memo": si.memo or "",
                "is_available": bool(si.is_available),
                "label": f"#{si.serial_no}",
                "display": f"{si.set_item.name} #{si.serial_no}",
            }
        )

    records = db.query(UsageRecord).filter(
        UsageRecord.status == "사용중",
        UsageRecord.room_no == room_no,
    ).order_by(UsageRecord.room_no, UsageRecord.surgery_order, UsageRecord.used_at).all()

    grouped_records = defaultdict(list)
    for r in records:
        key = f"{r.room_no}-{r.surgery_order}"
        grouped_records[key].append(r)

    ctx = template_ctx(request, active="or")
    ctx.update(
        {
            "departments": departments,
            "surgeries": surgeries,
            "defaults": defaults,
            "department_id": department_id,
            "surgery_id": surgery_id_int,
            "grouped_records": grouped_records,
            "room_no": room_no,
            "set_items": set_items,
            "single_items": single_items,
            "manual_surgery_name": manual_surgery_name,
            "surgery_order": surgery_order,
            "is_contaminated": is_contaminated,
            "set_instance_map_json": json.dumps(set_instance_map, ensure_ascii=False),
        }
    )
    return templates.TemplateResponse("or_use.html", ctx)


@app.post("/or-use/register")
def or_use_register(
    request: Request,
    surgery_order: int = Form(...),
    department_id: int = Form(...),
    surgery_id: Optional[int] = Form(None),
    manual_surgery_name: str = Form(""),
    pending_item_ids: str = Form(""),
    pending_set_instance_ids: str = Form(""),
    pending_manual_items: str = Form(""),
    is_contaminated: int = Form(0),
    db=Depends(db_dep),
):
    if request.session.get("role") != "or":
        return RedirectResponse("/login")

    room_no = request.session.get("room_no")
    dep = db.get(Department, department_id)
    surg = db.get(Surgery, surgery_id) if surgery_id else None
    surgery_name = manual_surgery_name.strip() or (surg.name if surg else "")

    item_ids = [int(x) for x in pending_item_ids.split(",") if x.strip()]
    set_instance_ids = [int(x) for x in pending_set_instance_ids.split(",") if x.strip()]
    manual_items = [x.strip() for x in pending_manual_items.split("|") if x.strip()]

    for item_id in item_ids:
        it = db.get(Item, item_id)
        if not it:
            continue
        if it.kind != "set" and it.status != "멸균완료/보관":
            continue
        if it.kind != "set":
            it.status = "OR 사용중"
        record = UsageRecord(
            case_date=dt.date.today(),
            room_no=room_no,
            surgery_order=surgery_order,
            department=dep.name if dep else "",
            surgery_name=surgery_name,
            item_id=it.id,
            status="사용중",
            used_at=now(),
            is_contaminated=bool(is_contaminated),
        )
        db.add(record)

    for si_id in set_instance_ids:
        si = db.get(SetInstance, si_id)
        if not si or not si.active:
            continue
        record = UsageRecord(
            case_date=dt.date.today(),
            room_no=room_no,
            surgery_order=surgery_order,
            department=dep.name if dep else "",
            surgery_name=surgery_name,
            item_id=si.set_item_id,
            set_instance_id=si.id,
            status="사용중",
            used_at=now(),
            is_contaminated=bool(is_contaminated),
        )
        db.add(record)

    for manual_name in manual_items:
        code = f"MANUAL-{manual_name[:20]}"
        item = db.query(Item).filter(Item.name == manual_name, Item.kind == "instrument").first()
        if not item:
            item = Item(code=code, name=manual_name, kind="instrument", category="일반", storage="수기입력", status="멸균완료/보관", active=True)
            db.add(item)
            db.flush()
        if item.status != "멸균완료/보관":
            continue
        item.status = "OR 사용중"
        db.add(UsageRecord(
            case_date=dt.date.today(), room_no=room_no, surgery_order=surgery_order,
            department=dep.name if dep else "", surgery_name=surgery_name,
            item_id=item.id, status="사용중", used_at=now(), is_contaminated=bool(is_contaminated),
        ))

    db.commit()
    manual_q = f"&manual_surgery_name={manual_surgery_name}" if manual_surgery_name.strip() else ""
    surgery_q = surgery_id if surgery_id else ""
    return RedirectResponse(f"/or-use?department_id={department_id}&surgery_id={surgery_q}&surgery_order={surgery_order}&is_contaminated={is_contaminated}{manual_q}", status_code=302)


def _mark_records_returned(ids: list[int], urgent: bool, db):
    for rid in ids:
        record = db.get(UsageRecord, rid)
        if not record:
            continue
        record.status = "반납"
        record.returned_at = now()
        record.is_urgent = urgent or bool(record.is_urgent)
        record.process_started_at = None
        record.process_due_at = None
        record.machine_key = None
        record.machine_name = None
        record.process_minutes = None
        if record.set_instance_id is None:
            item = db.get(Item, record.item_id)
            if item:
                item.status = "수거대기"


@app.post("/or-use/return-selected")
def or_return_selected(record_ids: str = Form(""), db=Depends(db_dep)):
    ids = [int(x) for x in record_ids.split(",") if x.strip()]
    _mark_records_returned(ids, urgent=False, db=db)
    db.commit()
    return RedirectResponse("/or-use", status_code=302)


@app.post("/or-use/wash-selected")
def or_wash_selected(record_ids: str = Form(""), db=Depends(db_dep)):
    ids = [int(x) for x in record_ids.split(",") if x.strip()]
    _mark_records_returned(ids, urgent=False, db=db)
    db.commit()
    return RedirectResponse("/or-use", status_code=302)


@app.post("/or-use/return-case")
def or_return_case(room_no: int = Form(...), surgery_order: int = Form(...), db=Depends(db_dep)):
    records = db.query(UsageRecord).filter(UsageRecord.room_no == room_no, UsageRecord.surgery_order == surgery_order, UsageRecord.status == "사용중").all()
    _mark_records_returned([r.id for r in records], urgent=False, db=db)
    db.commit()
    return RedirectResponse("/or-use", status_code=302)


@app.post("/or-use/urgent-selected")
def urgent_selected(record_ids: str = Form(...), db=Depends(db_dep)):
    ids = [int(x) for x in record_ids.split(",") if x]
    _mark_records_returned(ids, urgent=True, db=db)
    db.commit()
    return RedirectResponse("/or-use", status_code=302)


def get_machine_map(db):
    rows = db.query(MachineConfig).filter(MachineConfig.active == True).order_by(MachineConfig.process_type, MachineConfig.id).all()
    return {m.machine_key: m for m in rows}


def build_csr_groups(db, q: str = ""):
    query = db.query(UsageRecord).join(Item, UsageRecord.item_id == Item.id).filter(UsageRecord.status.in_([
        "반납", "반입확인", "세척중", "세척완료", "멸균중", "멸균완료", "불출"
    ]))
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    records = query.order_by(UsageRecord.room_no, UsageRecord.surgery_order, UsageRecord.returned_at, UsageRecord.used_at).all()
    buckets: dict[tuple[int,int], list[UsageRecord]] = defaultdict(list)
    for r in records:
        buckets[(r.room_no, r.surgery_order)].append(r)

    ordered = OrderedDict()
    for key in sorted(buckets.keys(), key=lambda k: (min(0 if x.is_urgent else 1 for x in buckets[k]), k[0], k[1])):
        recs = buckets[key]
        recs.sort(key=lambda r: (0 if r.is_urgent else 1, 0 if r.is_contaminated else 1, process_rank(r.status), r.returned_at or r.used_at or now()))
        ordered[key] = recs
    return ordered


def build_machine_board(db):
    order_keys = [
        'handwash', 'washer1', 'washer2',
        'steam1', 'steam2', 'steam3',
        'plasma1', 'plasma2', 'eo',
    ]
    all_rows = db.query(MachineConfig).filter(MachineConfig.active == True).all()
    keyed = {m.machine_key: m for m in all_rows}
    machines = [keyed[k] for k in order_keys if k in keyed] + [m for m in all_rows if m.machine_key not in order_keys]
    board = []
    for m in machines:
        active_rec = db.query(UsageRecord).filter(UsageRecord.machine_key == m.machine_key, UsageRecord.status.in_(["세척중", "멸균중"])).order_by(UsageRecord.process_started_at.desc()).first()
        board.append({
            "key": m.machine_key,
            "name": m.machine_name,
            "process_type": m.process_type,
            "duration": m.duration_minutes,
            "status": "사용중" if active_rec else "비어있음",
            "due_at": active_rec.process_due_at.isoformat() if active_rec and active_rec.process_due_at else "",
            "item_name": active_rec.item.name if active_rec else "",
        })
    return board


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, q: str = "", db=Depends(db_dep)):
    if not require_login(request):
        return RedirectResponse("/login")
    groups = build_csr_groups(db, q=q)
    machine_map = get_machine_map(db)
    ctx = template_ctx(request, active="dashboard")
    ctx.update({
        "groups": groups,
        "q": q,
        "machine_board": build_machine_board(db),
        "wash_machines": [m for m in machine_map.values() if m.process_type == "wash"],
        "ster_machines": [m for m in machine_map.values() if m.process_type == "ster"],
        "readonly": True,
    })
    return templates.TemplateResponse("csr.html", ctx)


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, db=Depends(db_dep)):
    if not require_login(request):
        return RedirectResponse("/login")

    total_items = db.query(Item).filter(Item.active == True).count()
    total_sets = db.query(Item).filter(Item.active == True, Item.kind == "set").count()
    total_instruments = db.query(Item).filter(Item.active == True, Item.kind == "instrument").count()
    today_usage = db.query(UsageRecord).filter(UsageRecord.case_date == dt.date.today()).count()

    raw_counts = (
        db.query(UsageRecord.status, text("count(*) as count"))
        .group_by(UsageRecord.status)
        .order_by(UsageRecord.status)
        .all()
    )
    status_counts = [{"status": row[0], "count": row[1]} for row in raw_counts]

    ctx = template_ctx(request, active="stats")
    ctx.update({
        "total_items": total_items,
        "total_sets": total_sets,
        "total_instruments": total_instruments,
        "today_usage": today_usage,
        "status_counts": status_counts,
        "machine_board": build_machine_board(db),
    })
    return templates.TemplateResponse("stats.html", ctx)


@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request, q: str = "", db=Depends(db_dep)):
    if request.session.get("role") not in {"csr", "admin"}:
        return RedirectResponse("/login")

    query = db.query(Item).filter(Item.active == True)
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    items = query.order_by(Item.kind.desc(), Item.category, Item.name).all()

    ctx = template_ctx(request, active="items")
    ctx.update({
        "items": items,
        "q": q,
        "total_items": db.query(Item).filter(Item.active == True).count(),
        "total_sets": db.query(Item).filter(Item.active == True, Item.kind == "set").count(),
        "total_instruments": db.query(Item).filter(Item.active == True, Item.kind == "instrument").count(),
    })
    return templates.TemplateResponse("items.html", ctx)


@app.get("/csr", response_class=HTMLResponse)
def csr_page(request: Request, q: str = "", db=Depends(db_dep)):
    if request.session.get("role") != "csr":
        return RedirectResponse("/login")
    groups = build_csr_groups(db, q=q)
    machine_map = get_machine_map(db)
    ctx = template_ctx(request, active="csr")
    ctx.update({
        "groups": groups,
        "q": q,
        "machine_board": build_machine_board(db),
        "wash_machines": [m for m in machine_map.values() if m.process_type == "wash"],
        "ster_machines": [m for m in machine_map.values() if m.process_type == "ster"],
        "readonly": False,
    })
    return templates.TemplateResponse("csr.html", ctx)


@app.get("/csr-view", response_class=HTMLResponse)
def csr_view_page(request: Request, q: str = "", db=Depends(db_dep)):
    if request.session.get("role") != "or":
        return RedirectResponse("/login")
    groups = build_csr_groups(db, q=q)
    machine_map = get_machine_map(db)
    ctx = template_ctx(request, active="csr")
    ctx.update({
        "groups": groups,
        "q": q,
        "machine_board": build_machine_board(db),
        "wash_machines": [m for m in machine_map.values() if m.process_type == "wash"],
        "ster_machines": [m for m in machine_map.values() if m.process_type == "ster"],
        "readonly": True,
    })
    return templates.TemplateResponse("csr.html", ctx)


@app.post("/csr/bulk")
def csr_bulk(
    request: Request,
    action: str = Form(...),
    record_ids: str = Form(""),
    machine_key: str = Form(""),
    minutes: int = Form(0),
    db=Depends(db_dep),
):
    if request.session.get("role") != "csr":
        return RedirectResponse("/login")
    ids = [int(x) for x in record_ids.split(",") if x.strip()]
    machine = db.query(MachineConfig).filter(MachineConfig.machine_key == machine_key).first() if machine_key else None
    n = now()

    for rid in ids:
        r = db.get(UsageRecord, rid)
        if not r:
            continue
        if action == "receive":
            r.status = "반입확인"
            r.csr_received_at = n
        elif action == "wash_start":
            use_min = minutes or (machine.duration_minutes if machine else 0)
            r.status = "세척중"
            r.process_started_at = n
            r.process_due_at = n + dt.timedelta(minutes=use_min)
            r.machine_key = machine.machine_key if machine else "handwash"
            r.machine_name = machine.machine_name if machine else "손세척"
            r.process_minutes = use_min
        elif action == "wash_done":
            r.status = "세척완료"
        elif action == "ster_start":
            use_min = minutes or (machine.duration_minutes if machine else 0)
            r.status = "멸균중"
            r.process_started_at = n
            r.process_due_at = n + dt.timedelta(minutes=use_min)
            r.machine_key = machine.machine_key if machine else None
            r.machine_name = machine.machine_name if machine else None
            r.process_minutes = use_min
            r.is_urgent = False
        elif action == "ster_done":
            r.status = "멸균완료"
            r.sterilized_at = n
        elif action == "release":
            r.status = "불출"
            r.release_requested_at = n
            if r.set_instance_id is None:
                item = db.get(Item, r.item_id)
                if item:
                    item.status = "멸균완료/보관"
        elif action == "toggle_urgent":
            r.is_urgent = not bool(r.is_urgent)
        elif action == "toggle_contam":
            r.is_contaminated = not bool(r.is_contaminated)
    db.commit()
    return RedirectResponse("/csr", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db=Depends(db_dep)):
    if request.session.get("role") != "admin":
        return RedirectResponse("/login")
    machines = db.query(MachineConfig).order_by(MachineConfig.process_type, MachineConfig.id).all()
    ctx = template_ctx(request, active="admin")
    ctx.update({"machines": machines, "admin_pin": ADMIN_PIN})
    return templates.TemplateResponse("admin.html", ctx)


@app.post("/admin/machine/update")
def admin_machine_update(request: Request, machine_id: int = Form(...), duration_minutes: int = Form(...), active: Optional[str] = Form(None), db=Depends(db_dep)):
    if request.session.get("role") != "admin":
        return RedirectResponse("/login")
    m = db.get(MachineConfig, machine_id)
    if m:
        m.duration_minutes = duration_minutes
        m.active = bool(active)
        db.commit()
    return RedirectResponse("/admin", status_code=302)
