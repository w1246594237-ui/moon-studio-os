from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from database import ensure_default_time_blocks, execute, init_db, query


st.set_page_config(page_title="Moon Studio OS", page_icon="🌙", layout="wide")
init_db()

PRIORITIES = ["P0", "P1", "P2", "P3"]
TASK_STATUSES = ["未开始", "进行中", "已完成", "延期", "取消"]
CONTENT_STATUSES = ["想法", "制作中", "待发布", "已发布", "已复盘"]
PLATFORMS = ["小红书", "Instagram", "小红书 + Instagram", "其他"]

st.markdown("""
<style>
  .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1320px;}
  [data-testid="stMetric"] {background: #f7f5fb; border: 1px solid #ebe7f2; padding: 14px; border-radius: 12px;}
  .protected {background:#f4efff; border-left:4px solid #7657c7; padding:12px 14px; border-radius:8px; margin:6px 0;}
  .hint {color:#6f6879; font-size:.92rem;}
</style>
""", unsafe_allow_html=True)


def projects() -> list[dict]:
    return query("SELECT * FROM projects ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, id")


def project_maps():
    rows = projects()
    return {p["name"]: p["id"] for p in rows}, {p["id"]: p["name"] for p in rows}


def optional_date(value):
    return value.isoformat() if value else None


def rerun(message: str):
    st.toast(message)
    st.rerun()


def delete_button(table: str, row_id: int, key: str):
    if st.button("删除", key=key, type="secondary"):
        execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        rerun("已删除")


def dashboard():
    today = date.today()
    ensure_default_time_blocks(today)
    st.title("🌙 Moon Studio OS")
    st.caption(f"{today.strftime('%Y年%m月%d日')} · 今天只关注真正重要的事")

    today_tasks = query("""
        SELECT t.*, p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
        WHERE t.status NOT IN ('取消') AND (t.deadline = ? OR t.status = '进行中')
        ORDER BY CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, t.deadline LIMIT 3
    """, (today.isoformat(),))
    all_today = query("SELECT status FROM tasks WHERE deadline = ? AND status != '取消'", (today.isoformat(),))
    done = sum(t["status"] == "已完成" for t in all_today)
    rate = round(done / len(all_today) * 100) if all_today else 0
    deadline = date(2026, 7, 22)
    days = (deadline - today).days

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日任务完成率", f"{rate}%", f"{done}/{len(all_today)} 项")
    c2.metric("今日最重要任务", f"{len(today_tasks)} 项")
    c3.metric("作品集冲刺", "已到截止日" if days == 0 else (f"还有 {days} 天" if days > 0 else "已过截止日"))
    week_start = today - timedelta(days=today.weekday())
    hours = query("""SELECT COALESCE(SUM(tb.actual_hours),0) hours FROM time_blocks tb
        LEFT JOIN projects p ON p.id=tb.project_id WHERE tb.block_date BETWEEN ? AND ? AND p.name='作品集冲刺'""",
        (week_start.isoformat(), today.isoformat()))[0]["hours"]
    c4.metric("本周作品集投入", f"{hours:g} 小时")

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("今日最重要 3 件事")
        if not today_tasks:
            st.info("还没有今日任务。去「任务管理」添加，或把任务设为进行中。")
        for task in today_tasks:
            a, b = st.columns([5, 1])
            a.markdown(f"**{task['priority']} · {task['name']}**  \n{task['project_name'] or '未归类'} · {task['status']}")
            if task["status"] != "已完成" and b.button("完成", key=f"dash_done_{task['id']}"):
                execute("UPDATE tasks SET status='已完成', progress=100, completed_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), task["id"]))
                rerun("任务已完成")

        st.subheader("今日时间安排")
        blocks = query("SELECT * FROM time_blocks WHERE block_date=? ORDER BY id", (today.isoformat(),))
        for b in blocks:
            css = "protected" if b["is_protected"] else ""
            lock = " 🔒" if b["is_protected"] else ""
            st.markdown(f"<div class='{css}'><b>{b['period']}{lock}</b><br>{b['plan']}</div>", unsafe_allow_html=True)

    with right:
        st.subheader("当前最重要提醒")
        if days >= 0:
            st.warning(f"作品集冲刺距离 7 月 22 日还有 {days} 天。13:30–18:00 是受保护的深度工作时间。")
        else:
            st.warning("作品集截止日期已过，请确认项目状态并调整求职优先级。")
        overdue = query("SELECT COUNT(*) n FROM tasks WHERE deadline < ? AND status NOT IN ('已完成','取消')", (today.isoformat(),))[0]["n"]
        if overdue:
            st.error(f"有 {overdue} 个逾期任务需要重新安排。")

        st.subheader("项目整体进度")
        for p in project_progress():
            st.write(f"**{p['name']}** · {p['priority']} · {p['progress']}%")
            st.progress(p["progress"] / 100)
            st.caption(p["next_action"] or "尚未设置下一步")


def project_progress():
    return query("""
    SELECT p.*,
      COUNT(t.id) task_count,
      COALESCE(ROUND(AVG(CASE WHEN t.status='取消' THEN NULL ELSE t.progress END)),0) progress,
      COALESCE(SUM(t.actual_hours),0) invested_hours
    FROM projects p LEFT JOIN tasks t ON p.id=t.project_id
    GROUP BY p.id ORDER BY CASE p.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END
    """)


def task_page():
    st.title("任务管理")
    name_to_id, id_to_name = project_maps()
    with st.expander("＋ 新建任务", expanded=False):
        with st.form("new_task", clear_on_submit=True):
            name = st.text_input("任务名称 *")
            c1, c2, c3 = st.columns(3)
            project = c1.selectbox("所属项目", ["未归类"] + list(name_to_id))
            task_type = c2.text_input("类型", placeholder="设计 / 内容 / 求职…")
            priority = c3.selectbox("优先级", PRIORITIES, index=1)
            c4, c5, c6 = st.columns(3)
            status = c4.selectbox("状态", TASK_STATUSES)
            has_deadline = c5.checkbox("设置截止日期", value=True)
            deadline = c6.date_input("截止日期", value=date.today()) if has_deadline else None
            e1, e2, e3 = st.columns(3)
            estimated = e1.number_input("预计耗时（小时）", 0.0, step=0.5)
            actual = e2.number_input("实际耗时（小时）", 0.0, step=0.5)
            progress = e3.slider("完成比例", 0, 100, 100 if status == "已完成" else 0)
            notes = st.text_area("备注")
            if st.form_submit_button("保存任务", type="primary"):
                if not name.strip(): st.error("请填写任务名称")
                else:
                    completed = datetime.now().isoformat(timespec="seconds") if status == "已完成" else None
                    execute("""INSERT INTO tasks (name,project_id,type,priority,status,deadline,estimated_hours,actual_hours,progress,notes,completed_at,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (name.strip(), name_to_id.get(project), task_type, priority, status, optional_date(deadline), estimated, actual, 100 if status == "已完成" else progress, notes, completed, datetime.now().isoformat(timespec="seconds")))
                    rerun("任务已创建")

    f1, f2, f3 = st.columns(3)
    status_filter = f1.selectbox("筛选状态", ["全部"] + TASK_STATUSES)
    project_filter = f2.selectbox("筛选项目", ["全部"] + list(name_to_id))
    priority_filter = f3.selectbox("筛选优先级", ["全部"] + PRIORITIES)
    clauses, params = [], []
    if status_filter != "全部": clauses.append("t.status=?"); params.append(status_filter)
    if project_filter != "全部": clauses.append("t.project_id=?"); params.append(name_to_id[project_filter])
    if priority_filter != "全部": clauses.append("t.priority=?"); params.append(priority_filter)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = query(f"SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id {where} ORDER BY CASE t.status WHEN '进行中' THEN 0 WHEN '未开始' THEN 1 WHEN '延期' THEN 2 ELSE 3 END, CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, t.deadline", params)
    if not rows: st.info("没有符合条件的任务。")
    for t in rows:
        label = f"{t['priority']} · {t['name']}　｜　{t['status']}　｜　{t['project_name'] or '未归类'}"
        with st.expander(label):
            with st.form(f"edit_task_{t['id']}"):
                name = st.text_input("任务名称", t["name"])
                c1, c2, c3 = st.columns(3)
                project_names = ["未归类"] + list(name_to_id)
                project = c1.selectbox("所属项目", project_names, index=project_names.index(id_to_name.get(t["project_id"], "未归类")))
                task_type = c2.text_input("类型", t["type"] or "")
                priority = c3.selectbox("优先级", PRIORITIES, index=PRIORITIES.index(t["priority"]))
                c4, c5, c6 = st.columns(3)
                status = c4.selectbox("状态", TASK_STATUSES, index=TASK_STATUSES.index(t["status"]))
                deadline = c5.date_input("截止日期", value=date.fromisoformat(t["deadline"]) if t["deadline"] else None)
                progress = c6.slider("完成比例", 0, 100, int(t["progress"]))
                h1, h2 = st.columns(2)
                estimated = h1.number_input("预计耗时", 0.0, value=float(t["estimated_hours"]), step=0.5)
                actual = h2.number_input("实际耗时", 0.0, value=float(t["actual_hours"]), step=0.5)
                notes = st.text_area("备注", t["notes"] or "")
                if st.form_submit_button("保存修改", type="primary"):
                    completed = t["completed_at"]
                    if status == "已完成" and not completed: completed = datetime.now().isoformat(timespec="seconds")
                    if status != "已完成": completed = None
                    execute("""UPDATE tasks SET name=?,project_id=?,type=?,priority=?,status=?,deadline=?,estimated_hours=?,actual_hours=?,progress=?,notes=?,completed_at=? WHERE id=?""",
                            (name, name_to_id.get(project), task_type, priority, status, optional_date(deadline), estimated, actual, 100 if status == "已完成" else progress, notes, completed, t["id"]))
                    rerun("任务已更新")
            delete_button("tasks", t["id"], f"del_task_{t['id']}")


def project_page():
    st.title("项目管理")
    for p in project_progress():
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.subheader(f"{p['name']} · {p['priority']}")
            c2.metric("完成", f"{p['progress']}%")
            st.progress(p["progress"] / 100)
            a, b, c = st.columns(3)
            a.write(f"**当前阶段**  \n{p['stage'] or '—'}")
            b.write(f"**截止日期**  \n{p['deadline'] or '长期项目'}")
            c.write(f"**任务 / 投入**  \n{p['task_count']} 项 / {p['invested_hours']:g} 小时")
            st.write(f"**目标：** {p['goal'] or '—'}")
            st.info(f"下一步行动：{p['next_action'] or '尚未设置'}")
            with st.expander("编辑项目"):
                with st.form(f"project_{p['id']}"):
                    goal = st.text_area("目标", p["goal"] or "")
                    x, y, z = st.columns(3)
                    stage = x.text_input("当前阶段", p["stage"] or "")
                    priority = y.selectbox("优先级", PRIORITIES, index=PRIORITIES.index(p["priority"]))
                    deadline = z.date_input("截止日期", value=date.fromisoformat(p["deadline"]) if p["deadline"] else None)
                    next_action = st.text_input("下一步行动", p["next_action"] or "")
                    if st.form_submit_button("保存"):
                        execute("UPDATE projects SET goal=?,stage=?,priority=?,deadline=?,next_action=? WHERE id=?", (goal, stage, priority, optional_date(deadline), next_action, p["id"]))
                        rerun("项目已更新")


def time_page():
    st.title("每日时间规划")
    selected = st.date_input("选择日期", date.today())
    ensure_default_time_blocks(selected)
    name_to_id, id_to_name = project_maps()
    blocks = query("SELECT * FROM time_blocks WHERE block_date=? ORDER BY id", (selected.isoformat(),))
    for b in blocks:
        icon = "🔒" if b["is_protected"] else "🕐"
        with st.expander(f"{icon} {b['period']} · {b['plan']}", expanded=b["is_protected"] == 1):
            with st.form(f"block_{b['id']}"):
                c1, c2 = st.columns(2)
                period = c1.text_input("时间段", b["period"])
                project_options = ["未归类"] + list(name_to_id)
                project = c2.selectbox("关联项目", project_options, index=project_options.index(id_to_name.get(b["project_id"], "未归类")))
                plan = st.text_input("计划事项", b["plan"])
                actual_result = st.text_area("实际完成情况", b["actual_result"] or "")
                actual_hours = st.number_input("实际耗时（小时）", 0.0, value=float(b["actual_hours"]), step=0.25)
                protected = st.checkbox("保护该时间段", value=bool(b["is_protected"]))
                if st.form_submit_button("保存"):
                    execute("UPDATE time_blocks SET period=?,plan=?,actual_result=?,actual_hours=?,project_id=?,is_protected=? WHERE id=?", (period, plan, actual_result, actual_hours, name_to_id.get(project), int(protected), b["id"]))
                    rerun("时间记录已保存")
    with st.expander("＋ 添加时间块"):
        with st.form("new_block", clear_on_submit=True):
            period = st.text_input("时间段", placeholder="例如 10:00-11:30")
            plan = st.text_input("计划事项")
            project = st.selectbox("关联项目", ["未归类"] + list(name_to_id))
            if st.form_submit_button("添加"):
                if period and plan:
                    execute("INSERT INTO time_blocks (block_date,period,plan,project_id) VALUES (?,?,?,?)", (selected.isoformat(), period, plan, name_to_id.get(project)))
                    rerun("时间块已添加")
                else: st.error("请填写时间段和计划事项")
    week_start = selected - timedelta(days=selected.weekday())
    weekly = query("""SELECT tb.block_date, COALESCE(SUM(tb.actual_hours),0) hours FROM time_blocks tb JOIN projects p ON p.id=tb.project_id
        WHERE p.name='作品集冲刺' AND tb.block_date BETWEEN ? AND ? GROUP BY tb.block_date ORDER BY tb.block_date""", (week_start.isoformat(), (week_start+timedelta(days=6)).isoformat()))
    st.subheader("本周作品集投入")
    st.metric("合计", f"{sum(x['hours'] for x in weekly):g} 小时")
    if weekly: st.bar_chart(pd.DataFrame(weekly).set_index("block_date"))


def content_page(brand: str):
    is_bree = brand == "Bree"
    st.title(f"{brand} 内容管理")
    if not is_bree: st.caption("定位探索阶段：记录真实的设计实践与个人表达，不以教程数量为目标。")
    types = (["Bree日记", "今天发现", "插画", "角色设定", "雷诺曼", "创作过程"] if is_bree else ["AI实验", "设计思考", "创作记录", "工具分享", "作品集过程"])
    with st.expander("＋ 新建内容"):
        with st.form(f"new_content_{brand}", clear_on_submit=True):
            title = st.text_input("标题 *")
            a, b, c = st.columns(3)
            content_type = a.selectbox("内容类型", types)
            platform = b.selectbox("平台", PLATFORMS)
            status = c.selectbox("发布状态", CONTENT_STATUSES)
            publish = st.date_input("发布时间", value=None)
            production = st.number_input("制作时间（小时）", 0.0, step=0.5)
            copywriting = st.text_area("文案")
            notes = st.text_area("备注")
            if st.form_submit_button("保存内容", type="primary"):
                if title.strip():
                    execute("""INSERT INTO contents (brand,title,content_type,platform,status,publish_at,production_hours,copywriting,notes,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""", (brand, title, content_type, platform, status, optional_date(publish), production, copywriting, notes, datetime.now().isoformat(timespec="seconds")))
                    rerun("内容已创建")
                else: st.error("请填写标题")
    rows = query("SELECT * FROM contents WHERE brand=? ORDER BY CASE status WHEN '制作中' THEN 0 WHEN '待发布' THEN 1 WHEN '想法' THEN 2 ELSE 3 END, id DESC", (brand,))
    if not rows: st.info("内容库还是空的。先记录一个想法即可，不需要立刻制作。")
    for r in rows:
        with st.expander(f"{r['status']} · {r['title']}　｜　{r['content_type']} · {r['platform']}"):
            with st.form(f"content_{brand}_{r['id']}"):
                title = st.text_input("标题", r["title"])
                a, b, c = st.columns(3)
                content_type = a.selectbox("内容类型", types, index=types.index(r["content_type"]) if r["content_type"] in types else 0)
                platform = b.selectbox("平台", PLATFORMS, index=PLATFORMS.index(r["platform"]) if r["platform"] in PLATFORMS else 0)
                status = c.selectbox("状态", CONTENT_STATUSES, index=CONTENT_STATUSES.index(r["status"]))
                publish = st.date_input("发布时间", value=date.fromisoformat(r["publish_at"]) if r["publish_at"] else None)
                production = st.number_input("制作时间（小时）", 0.0, value=float(r["production_hours"]), step=0.5)
                copywriting = st.text_area("文案", r["copywriting"] or "")
                notes = st.text_area("备注", r["notes"] or "")
                st.markdown("**发布数据**")
                m1, m2, m3, m4, m5 = st.columns(5)
                views = m1.number_input("浏览", 0, value=int(r["views"]))
                likes = m2.number_input("点赞", 0, value=int(r["likes"]))
                saves = m3.number_input("收藏", 0, value=int(r["saves"]))
                comments = m4.number_input("评论", 0, value=int(r["comments"]))
                followers = m5.number_input("涨粉", 0, value=int(r["followers_gained"]))
                review = st.text_area("复盘总结", r["review_summary"] or "", placeholder="为什么效果好/不好？下一次继续或停止什么？")
                if st.form_submit_button("保存修改", type="primary"):
                    execute("""UPDATE contents SET title=?,content_type=?,platform=?,status=?,publish_at=?,production_hours=?,copywriting=?,notes=?,views=?,likes=?,saves=?,comments=?,followers_gained=?,review_summary=? WHERE id=?""",
                        (title, content_type, platform, status, optional_date(publish), production, copywriting, notes, views, likes, saves, comments, followers, review, r["id"]))
                    rerun("内容已更新")
            delete_button("contents", r["id"], f"del_content_{brand}_{r['id']}")


def ideas_page():
    st.title("想法池")
    st.caption("先收集，后评估。新想法不需要打断今天的计划。")
    statuses = ["待评估", "保留", "执行", "放弃"]
    with st.form("new_idea", clear_on_submit=True):
        name = st.text_input("想法名称 *")
        description = st.text_area("描述")
        a, b = st.columns(2)
        idea_type = a.text_input("类型", placeholder="Bree / Moon / 作品集 / 其他")
        value = b.text_input("价值判断", placeholder="它解决什么问题？")
        if st.form_submit_button("放入想法池", type="primary"):
            if name.strip():
                execute("INSERT INTO ideas (name,description,type,created_at,value_judgment) VALUES (?,?,?,?,?)", (name, description, idea_type, datetime.now().isoformat(timespec="seconds"), value))
                rerun("想法已收好，继续当前计划吧")
            else: st.error("请填写想法名称")
    status_filter = st.selectbox("筛选", ["全部"] + statuses)
    sql, params = "SELECT * FROM ideas", []
    if status_filter != "全部": sql += " WHERE status=?"; params.append(status_filter)
    rows = query(sql + " ORDER BY id DESC", params)
    for r in rows:
        with st.expander(f"{r['status']} · {r['name']}"):
            with st.form(f"idea_{r['id']}"):
                description = st.text_area("描述", r["description"] or "")
                a, b, c = st.columns(3)
                idea_type = a.text_input("类型", r["type"] or "")
                value = b.text_input("价值判断", r["value_judgment"] or "")
                status = c.selectbox("状态", statuses, index=statuses.index(r["status"]))
                will_execute = st.checkbox("确认执行", value=bool(r["will_execute"]))
                if st.form_submit_button("保存"):
                    execute("UPDATE ideas SET description=?,type=?,value_judgment=?,status=?,will_execute=? WHERE id=?", (description, idea_type, value, status, int(will_execute), r["id"]))
                    rerun("想法已更新")
            delete_button("ideas", r["id"], f"del_idea_{r['id']}")


def review_page():
    st.title("周复盘")
    today = date.today()
    default_start = today - timedelta(days=today.weekday())
    week_start = st.date_input("选择周（建议选择周一）", default_start)
    week_start = week_start - timedelta(days=week_start.weekday())
    week_end = week_start + timedelta(days=6)
    st.caption(f"{week_start.isoformat()} — {week_end.isoformat()}")
    completed_tasks = query("SELECT name FROM tasks WHERE date(completed_at) BETWEEN ? AND ?", (week_start.isoformat(), week_end.isoformat()))
    unfinished_tasks = query("SELECT name FROM tasks WHERE deadline BETWEEN ? AND ? AND status NOT IN ('已完成','取消')", (week_start.isoformat(), week_end.isoformat()))
    existing = query("SELECT * FROM weekly_reviews WHERE week_start=?", (week_start.isoformat(),))
    r = existing[0] if existing else {}
    with st.form("weekly_review"):
        completed = st.text_area("本周完成", r.get("completed") or "\n".join(f"- {x['name']}" for x in completed_tasks))
        unfinished = st.text_area("本周未完成", r.get("unfinished") or "\n".join(f"- {x['name']}" for x in unfinished_tasks))
        reasons = st.text_area("原因", r.get("reasons", ""))
        over_time = st.text_area("哪些事情耗时超过预期", r.get("over_time", ""))
        good_content = st.text_area("哪些内容数据较好", r.get("good_content", ""))
        continue_tests = st.text_area("哪些内容值得继续测试", r.get("continue_tests", ""))
        next_three = st.text_area("下周三个重点", r.get("next_three", ""), placeholder="1.\n2.\n3.")
        stop_doing = st.text_area("停止事项", r.get("stop_doing", ""))
        if st.form_submit_button("保存本周复盘", type="primary"):
            execute("""INSERT INTO weekly_reviews (week_start,completed,unfinished,reasons,over_time,good_content,continue_tests,next_three,stop_doing,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(week_start) DO UPDATE SET completed=excluded.completed,unfinished=excluded.unfinished,reasons=excluded.reasons,over_time=excluded.over_time,good_content=excluded.good_content,continue_tests=excluded.continue_tests,next_three=excluded.next_three,stop_doing=excluded.stop_doing,updated_at=excluded.updated_at""",
                (week_start.isoformat(), completed, unfinished, reasons, over_time, good_content, continue_tests, next_three, stop_doing, datetime.now().isoformat(timespec="seconds")))
            rerun("周复盘已保存")


PAGES = {
    "首页 Dashboard": dashboard,
    "任务管理": task_page,
    "项目管理": project_page,
    "每日时间规划": time_page,
    "Bree 内容管理": lambda: content_page("Bree"),
    "Moon 内容管理": lambda: content_page("Moon"),
    "想法池": ideas_page,
    "周复盘": review_page,
}

with st.sidebar:
    st.title("🌙 Moon Studio OS")
    st.caption("一个人的长期工作台")
    page = st.radio("导航", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption("先完成今天最重要的事。")

PAGES[page]()

