"""쇼핑 리스트 Streamlit 앱."""

import re
import uuid
from datetime import datetime

import streamlit as st

import storage

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

NAME_MAX_LEN = 50
QTY_MIN, QTY_MAX = 1, 999
FILTERS = ["전체", "미완료", "완료"]


def init_state() -> None:
    """세션 상태를 초기화한다. 다른 탭/기기의 변경이 보이도록 목록은 매 실행마다 파일에서 새로 읽는다."""
    st.session_state.shopping_items = storage.load()
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "confirm_clear_all" not in st.session_state:
        st.session_state.confirm_clear_all = False
    if "add_quantity" not in st.session_state:
        st.session_state.add_quantity = 1


def new_item(name: str, quantity: int = 1, memo: str = "") -> dict:
    """PRD 5장 데이터 모델에 맞는 아이템을 만든다."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "memo": memo,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def validate(name: str, quantity) -> tuple[str, int, str | None]:
    """입력값을 정리하고 (품목명, 수량, 오류 메시지)를 반환한다. 오류가 없으면 메시지는 None."""
    name = (name or "").strip()
    if not name:
        return name, quantity, "품목명을 입력해 주세요."
    if len(name) > NAME_MAX_LEN:
        return name, quantity, f"품목명은 {NAME_MAX_LEN}자 이하로 입력해 주세요."
    if quantity is None or not QTY_MIN <= int(quantity) <= QTY_MAX:
        return name, quantity, f"수량은 {QTY_MIN}~{QTY_MAX} 사이로 입력해 주세요."
    return name, int(quantity), None


def escape_md(text: str) -> str:
    """사용자 입력이 서식으로 해석되지 않게 ASCII 기호를 HTML 문자 참조로 바꾼다.

    역슬래시 이스케이프는 URL 자동 링크 안에 역슬래시가 그대로 남고, Streamlit 전용 문법(:red[], :material/...:)은
    막지 못한다. 문자 참조는 마크다운 해석이 끝난 뒤에 글자로 풀리므로 어떤 서식도 만들지 않는다.
    """
    return re.sub(r"[!-/:-@\[-`{-~]", lambda m: f"&#{ord(m.group())};", text)


def find_item(item_id: str) -> dict | None:
    return next((i for i in st.session_state.shopping_items if i["id"] == item_id), None)


def mutate(change) -> None:
    """최신 파일 위에서 change를 적용·저장하고 세션 목록을 갱신한다."""
    st.session_state.shopping_items = storage.update(change)


def fill_edit_fields(item: dict) -> None:
    st.session_state[f"edit_name_{item['id']}"] = item["name"]
    st.session_state[f"edit_quantity_{item['id']}"] = item["quantity"]
    st.session_state[f"edit_memo_{item['id']}"] = item["memo"]


# ---------- 콜백: 모든 상태 변경은 여기서만 일어난다 ----------

def add_item() -> None:
    name, quantity, error = validate(st.session_state.add_name, st.session_state.add_quantity)
    if error:
        st.session_state.add_error = error
        return
    memo = (st.session_state.add_memo or "").strip()
    item = new_item(name, quantity, memo)
    mutate(lambda items: items + [item])
    # 성공했을 때만 입력칸을 비운다 (실패하면 입력값 유지)
    st.session_state.add_name = ""
    st.session_state.add_quantity = 1
    st.session_state.add_memo = ""
    st.toast(f"'{escape_md(name)}' 추가됨")


def toggle_checked(item_id: str) -> None:
    checked = st.session_state[f"check_{item_id}"]

    def change(items):
        for i in items:
            if i["id"] == item_id:
                i["checked"] = checked
        return items

    mutate(change)


def start_edit(item_id: str) -> None:
    item = find_item(item_id)
    if not item:
        return
    st.session_state.editing_id = item_id
    fill_edit_fields(item)


def save_edit(item_id: str) -> None:
    name, quantity, error = validate(
        st.session_state[f"edit_name_{item_id}"], st.session_state[f"edit_quantity_{item_id}"]
    )
    if error:
        st.session_state.edit_error = error
        return
    memo = (st.session_state[f"edit_memo_{item_id}"] or "").strip()
    found = False

    def change(items):
        nonlocal found
        for i in items:
            if i["id"] == item_id:
                i.update(name=name, quantity=quantity, memo=memo)
                found = True
        return items

    mutate(change)
    st.session_state.editing_id = None
    if found:
        st.toast(f"'{escape_md(name)}' 수정됨")
    else:
        st.toast("다른 곳에서 이미 삭제된 아이템이에요.")


def cancel_edit() -> None:
    st.session_state.editing_id = None


def delete_item(item_id: str) -> None:
    removed = []

    def change(items):
        removed.extend(i for i in items if i["id"] == item_id)
        return [i for i in items if i["id"] != item_id]

    mutate(change)
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    if removed:
        st.toast(f"'{escape_md(removed[0]['name'])}' 삭제됨")


def clear_checked() -> None:
    removed = 0

    def change(items):
        nonlocal removed
        remaining = [i for i in items if not i["checked"]]
        removed = len(items) - len(remaining)
        return remaining

    mutate(change)
    st.toast(f"완료 항목 {removed}개 삭제됨")


def set_confirm_clear_all(value: bool) -> None:
    st.session_state.confirm_clear_all = value


def clear_all() -> None:
    mutate(lambda items: [])
    st.session_state.editing_id = None
    st.session_state.confirm_clear_all = False
    st.toast("전체 삭제됨")


# ---------- 렌더링 ----------

CSS = """
<style>
/* 기본 상단 여백이 커서 모바일에서 첫 화면을 많이 차지함 */
[data-testid="stMainBlockContainer"] {
    padding-top: 3rem;
}
/* 편집 중인 행 강조 */
[class*="st-key-editrow_"] {
    background: #EEF7F1;
    border-color: #2E9E5B !important;
}
/* 완료된 행은 흐리게 */
[class*="st-key-row_done_"] {
    background: #FAFBFA;
}
/* 긴 품목명이어도 버튼이 다음 줄로 밀리지 않게: 행은 줄바꿈 금지, 텍스트가 남는 폭을 차지하고 줄바꿈 */
[class*="st-key-row_"] {
    flex-wrap: nowrap !important;
}
[class*="st-key-row_"] > [data-testid="stElementContainer"]:nth-child(2) {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    overflow-wrap: anywhere;
}
/* 체크박스 터치 영역 확보 (기본 26x20px -> 44px) */
[class*="st-key-row_"] [data-testid="stCheckbox"] label {
    min-width: 2.75rem;
    min-height: 2.75rem;
    justify-content: center;
    align-items: center;
}
/* 아이템 행 버튼 터치 영역 확보 */
[class*="st-key-row_"] button {
    min-width: 2.5rem;
    min-height: 2.5rem;
}
</style>
"""


def render_header() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🛒 쇼핑 리스트")
    items = st.session_state.shopping_items
    total = len(items)
    done = sum(1 for i in items if i["checked"])
    with st.container(horizontal=True, gap="small"):
        st.metric("전체", total, border=True, width="stretch")
        st.metric("남은", total - done, border=True, width="stretch")
        st.metric("완료", done, border=True, width="stretch")
    ratio = done / total if total else 0.0
    st.progress(ratio, text=f"진행률 {ratio:.0%}")


def render_add_form() -> None:
    with st.form("add_form"):
        col_name, col_qty, col_memo = st.columns([0.5, 0.2, 0.3], vertical_alignment="bottom")
        col_name.text_input("품목명", key="add_name", max_chars=NAME_MAX_LEN, placeholder="예: 우유")
        # min/max를 위젯에 주면 범위 밖 입력이 경고 없이 이전 값으로 바뀌므로, 범위 검사는 validate에서 한다
        col_qty.number_input("수량", key="add_quantity", step=1)
        col_memo.text_input("메모", key="add_memo", placeholder="선택")
        st.form_submit_button("추가", on_click=add_item, type="primary", icon=":material/add:", width="stretch")
    if error := st.session_state.pop("add_error", None):
        st.warning(error, icon=":material/warning:")


def item_markdown(item: dict) -> str:
    name = escape_md(item["name"])
    qty = f"x{item['quantity']}"
    if item["checked"]:
        text = f":gray[~~{name}~~] :gray-badge[{qty}]"
    else:
        text = f"**{name}** :green-badge[{qty}]"
    if item["memo"]:
        text += f"  \n:small[:gray[{escape_md(item['memo'])}]]"
    return text


def render_item_row(item: dict) -> None:
    item_id = item["id"]
    if st.session_state.editing_id == item_id:
        render_edit_row(item)
        return

    row_key = f"row_done_{item_id}" if item["checked"] else f"row_{item_id}"
    # 다른 탭에서 바뀐 체크 상태가 반영되도록 위젯 값을 매번 파일 기준으로 맞춘다
    st.session_state[f"check_{item_id}"] = item["checked"]
    with st.container(border=True, key=row_key, horizontal=True, vertical_alignment="center", gap="small"):
        st.checkbox(
            item["name"],
            key=f"check_{item_id}",
            on_change=toggle_checked,
            args=(item_id,),
            label_visibility="collapsed",
        )
        st.markdown(item_markdown(item), width="stretch")
        st.button("", icon=":material/edit:", key=f"edit_{item_id}", on_click=start_edit, args=(item_id,),
                  help="수정", type="tertiary")
        st.button("", icon=":material/delete:", key=f"del_{item_id}", on_click=delete_item, args=(item_id,),
                  help="삭제", type="tertiary")


def render_edit_row(item: dict) -> None:
    item_id = item["id"]
    # 편집 칸이 한 번이라도 화면에서 빠지면 Streamlit이 값을 지우므로, 비어 있으면 아이템 값으로 다시 채운다
    if f"edit_name_{item_id}" not in st.session_state:
        fill_edit_fields(item)
    with st.container(border=True, key=f"editrow_{item_id}"):
        st.caption(":material/edit: 수정 중")
        col_name, col_qty, col_memo = st.columns([0.5, 0.2, 0.3])
        col_name.text_input("품목명", key=f"edit_name_{item_id}", max_chars=NAME_MAX_LEN)
        col_qty.number_input("수량", key=f"edit_quantity_{item_id}", step=1)
        col_memo.text_input("메모", key=f"edit_memo_{item_id}")
        if error := st.session_state.pop("edit_error", None):
            st.warning(error, icon=":material/warning:")
        with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
            st.button("취소", key=f"cancel_{item_id}", on_click=cancel_edit)
            st.button("저장", key=f"save_{item_id}", on_click=save_edit, args=(item_id,), type="primary",
                      icon=":material/check:")


def render_item_list() -> None:
    items = st.session_state.shopping_items
    if st.session_state.editing_id not in {i["id"] for i in items}:
        st.session_state.editing_id = None
    if not items:
        st.session_state.confirm_clear_all = False
        st.info("아직 추가된 아이템이 없어요. 위에서 추가해 보세요!", icon=":material/shopping_cart:")
        return

    done = sum(1 for i in items if i["checked"])
    counts = {"전체": len(items), "미완료": len(items) - done, "완료": done}
    selected = st.segmented_control(
        "필터", FILTERS, key="filter", default="전체", required=True,
        format_func=lambda f: f"{f} {counts[f]}", label_visibility="collapsed", width="stretch",
    )
    # 미완료가 위, 완료가 아래 (같은 그룹 안에서는 추가된 순서 유지)
    visible = sorted(items, key=lambda i: i["checked"])
    # 편집 중인 아이템은 필터와 관계없이 보여서 입력 중인 내용이 사라지지 않게 한다
    editing = st.session_state.editing_id
    if selected == "미완료":
        visible = [i for i in visible if not i["checked"] or i["id"] == editing]
    elif selected == "완료":
        visible = [i for i in visible if i["checked"] or i["id"] == editing]

    if not visible:
        st.caption(f"'{selected}' 항목이 없어요.")
    for item in visible:
        render_item_row(item)

    if not st.session_state.confirm_clear_all:
        with st.container(horizontal=True, horizontal_alignment="distribute", gap="small"):
            st.button("완료 항목 모두 삭제", on_click=clear_checked, disabled=done == 0,
                      icon=":material/playlist_remove:")
            st.button("전체 삭제", on_click=set_confirm_clear_all, args=(True,), type="tertiary",
                      icon=":material/delete_sweep:")
    else:
        with st.container(border=True):
            st.warning(f"아이템 {len(items)}개를 모두 삭제할까요? 되돌릴 수 없어요.", icon=":material/warning:")
            with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
                st.button("취소", key="cancel_clear_all", on_click=set_confirm_clear_all, args=(False,))
                st.button("삭제", on_click=clear_all, type="primary")


def main() -> None:
    init_state()
    render_header()
    render_add_form()
    render_item_list()


main()
