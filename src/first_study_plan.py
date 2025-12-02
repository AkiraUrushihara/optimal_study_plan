"""学習計画を作る簡単な対話型スクリプト

使い方（実行すると対話で入力を受け取ります）:
 - 科目名、利用可能時間（合計時間: 時間単位）、学習日数を入力
 - タスク数を入力し、各タスクについて: 名前、問題数、1問あたりの所要時間(時間)、難易度係数、優先度を入力
 - 優先度の高いタスクから、各日ごとに可能な問題数を割り当てます
"""

from math import floor
import json
import csv
import os
from datetime import datetime

# --- オプション: ファイル内で値を定義して対話入力をスキップできます ---
# 例:
# SUBJECT_PRESET = "数学"
# DAY_CAPACITIES_PRESET = [1.0, 0.5, 2.0]  # 各日ごとの利用可能時間
# COMMON_TIME_PER_ITEM_PRESET = 0.5  # 全タスク共通の1問あたり時間
# TASKS_PRESET = [
#     {"name": "教科書問題", "total": 10, "priority": 1, "difficulty": 1.0},
#     {"name": "過去問", "total": 5, "priority": 2, "difficulty": 1.2},
# ]
# デフォルトでは None。編集して値を入れると対話入力をスキップします。
SUBJECT_PRESET = "例)数学"
DAY_CAPACITIES_PRESET = [2.0,3.0,3.0,3.0,3.0,8.0,8.0]
COMMON_TIME_PER_ITEM_PRESET = 0.5
TASKS_PRESET = [
    {"name": "例)演習プリント", "total": 8, "priority": 2, "difficulty": 1.0},
    {"name": "例)授業プリント", "total": 4, "priority": 3, "difficulty": 3.0},
    {"name": "例)教科書問題", "total": 27, "priority": 1, "difficulty": 1.0},
    {"name": "例)過去問", "total": 2, "priority": 4, "difficulty": 4.0},
]
# 日付関連のプリセット: Day1 の日付（ISO 形式 'YYYY-MM-DD'）とテスト日（任意、同じ形式）
# ここに日付文字列を設定すると CSV に保存され、他ツールで利用できます。
START_DATE_PRESET = "2025-12-01"
TEST_DATE_PRESET = "2025-12-08"
# ------------------------------------------------------------------


def prompt_float(prompt, default=None):
    while True:
        try:
            s = input(prompt)
            if s == "" and default is not None:
                return default
            return float(s)
        except ValueError:
            print("数値を入力してください（例: 1.5）")


def prompt_int(prompt, default=None):
    while True:
        try:
            s = input(prompt)
            if s == "" and default is not None:
                return default
            return int(s)
        except ValueError:
            print("整数を入力してください（例: 3）")


def collect_inputs():
    # このスクリプトはコード内プリセットで実行する想定です。
    # プリセットが未設定の場合は明示的にエラーを出して停止します。
    if SUBJECT_PRESET is None or DAY_CAPACITIES_PRESET is None or COMMON_TIME_PER_ITEM_PRESET is None or TASKS_PRESET is None:
        raise RuntimeError("プリセットが設定されていません。ファイル内の SUBJECT_PRESET / DAY_CAPACITIES_PRESET / COMMON_TIME_PER_ITEM_PRESET / TASKS_PRESET を編集してください。")

    subject = SUBJECT_PRESET
    day_hours = list(DAY_CAPACITIES_PRESET)
    total_available = sum(day_hours)
    common_time_per_item = COMMON_TIME_PER_ITEM_PRESET
    tasks = []
    for src in TASKS_PRESET:
        tasks.append({
            "name": src["name"],
            "remaining": int(src.get("total", 0)),
            "total": int(src.get("total", 0)),
            "time_per_item": common_time_per_item,
            "difficulty": float(src.get("difficulty", 1.0)),
            "priority": int(src.get("priority", 99)),
        })

    print(f"プリセットを使用します: 科目={subject}, 合計時間={total_available:.2f} 時間, 日数={len(day_hours)}")
    return subject, day_hours, total_available, tasks


def compute_total_time(tasks):
    total = 0.0
    for t in tasks:
        total += t["total"] * t["time_per_item"] * t["difficulty"]
    return total


def allocate_by_priority(day_capacities, tasks):
    # 日ごとに埋めていく方式：各日について利用可能時間を使い切るよう
    # 優先度順（数値が小さいほど高優先度と扱う）にタスクを割り当てます。
    # 同一優先度内では残数が多いものを先に割り当てることで、重要な大きなタスク
    # を前倒しで処理しやすくします。
    days = len(day_capacities)
    plan = [[] for _ in range(days)]

    # 各日を先頭から処理していく
    for day in range(days):
        remaining_time = float(day_capacities[day])
        any_assigned_today = False

        # その日の割当ループ：毎パスで優先度順に並べ替えて割当を試みる
        while True:
            assigned_in_pass = False

            # 優先度（小さい値が高優先度）→ 残数（大きいもの優先）の順でソート
            tasks_sorted = sorted(tasks, key=lambda x: (x.get("priority", 99), -int(x.get("remaining", 0))))

            for t in tasks_sorted:
                if t.get("remaining", 0) <= 0:
                    continue
                time_per = t.get("time_per_item", 0) * t.get("difficulty", 1.0)
                if time_per <= 0:
                    # 所要時間が不正ならスキップ
                    continue

                # その日の残時間に何問入るか
                if remaining_time >= time_per:
                    max_items = int(floor(remaining_time / time_per))
                    assign = min(max_items, t["remaining"])
                    if assign <= 0:
                        continue
                    # 割当
                    t["remaining"] -= assign
                    remaining_time -= assign * time_per
                    plan[day].append({"name": t["name"], "assigned": assign, "time": assign * time_per})
                    assigned_in_pass = True
                    any_assigned_today = True
                # 余裕がない場合は次のタスクを試す

            # パスで何も割り当てられなかった場合、
            # まだタスクが残っていれば "最低1問" ルールで1問を割り当てる
            if not assigned_in_pass:
                # まだ割当が1件も無く、日として多少の時間がある場合は1問だけ割当
                if (not any_assigned_today) and remaining_time > 0:
                    # 同様に優先度順で1問だけ割当
                    tasks_sorted = sorted(tasks, key=lambda x: (x.get("priority", 99), -int(x.get("remaining", 0))))
                    for t in tasks_sorted:
                        if t.get("remaining", 0) <= 0:
                            continue
                        time_per = t.get("time_per_item", 0) * t.get("difficulty", 1.0)
                        if time_per <= 0:
                            continue
                        # 1問割り当て（残時間が足りなくても強制割当）
                        t["remaining"] -= 1
                        remaining_time -= time_per
                        plan[day].append({"name": t["name"], "assigned": 1, "time": time_per})
                        any_assigned_today = True
                        assigned_in_pass = True
                        break

            # もう割当できるものが無ければこの日の処理を終える
            if not assigned_in_pass:
                break

    return plan


def print_plan(subject, total_available, day_capacities, tasks, total_needed, plan):
    days = len(day_capacities)
    print('\n' + '='*40)
    print(f"科目: {subject}")
    print(f"合計利用可能時間: {total_available:.2f} 時間")
    print(f"必要な総学習時間: {total_needed:.2f} 時間")
    print(f"学習日数: {days}")
    print('='*40 + '\n')

    print("各日の利用可能時間:")
    for i, h in enumerate(day_capacities, start=1):
        print(f"  Day {i}: {h:.2f} 時間")
    print('')

    if total_needed <= total_available:
        print("すべてのタスクを完了するための十分な時間があります。\n")
    else:
        print("注意: 利用可能時間より必要時間が多いです。計画を調整してください。\n")

    for i, day_tasks in enumerate(plan, start=1):
        print(f"Day {i}:")
        if not day_tasks:
            # 空日はプレースホルダを出さず、タスク行を出力しない
            pass
        else:
            for it in day_tasks:
                print(f"  - {it['name']} を {it['assigned']} 問（合計 {it['time']:.2f} 時間）")
        print('')

    # 残りタスクを表示
    remaining = [t for t in tasks if t["remaining"] > 0]
    if remaining:
        print("割り当て後に残ったタスク:")
        for t in remaining:
            est = t["remaining"] * t["time_per_item"] * t["difficulty"]
            print(f"  - {t['name']}: 残り {t['remaining']} 問（推定 {est:.2f} 時間）")
        print('\n利用可能時間内に収めるには、問題数を減らすか、1問あたりの時間/難易度を見直してください。')


def _export_plan_json(path, subject, day_capacities, plan):
    data = {
        "subject": subject,
        "generated_at": datetime.now().isoformat(),
        "day_capacities": day_capacities,
        "plan": []
    }
    for i, day_tasks in enumerate(plan, start=1):
        data["plan"].append({
            "day": i,
            "tasks": day_tasks
        })
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _export_plan_csv(path, subject, day_capacities, tasks, total_needed, plan):
    # CSV にメタ情報、日別容量、プラン、最後に人間向けレポート行をまとめて書く
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # メタ情報
        writer.writerow(["subject", subject])
        writer.writerow(["generated_at", datetime.now().isoformat()])
        writer.writerow(["total_available", f"{sum(day_capacities):.2f}"])
        writer.writerow(["total_needed", f"{total_needed:.2f}"])
        # 日付メタ（オプション）
        try:
            if START_DATE_PRESET is not None:
                writer.writerow(["start_date", str(START_DATE_PRESET)])
        except NameError:
            pass
        try:
            if TEST_DATE_PRESET is not None:
                writer.writerow(["test_date", str(TEST_DATE_PRESET)])
        except NameError:
            pass
        writer.writerow([])

        # 日別容量セクション
        writer.writerow(["Day Capacities"])
        writer.writerow(["Day", "AvailableHours"])
        for i, h in enumerate(day_capacities, start=1):
            writer.writerow([i, f"{h:.2f}"])
        writer.writerow([])

        # プラン本体
        writer.writerow(["Plan"])
        writer.writerow(["Day", "Task", "Assigned", "Time(hours)"])
        for i, day_tasks in enumerate(plan, start=1):
            if not day_tasks:
                # 以前は空日の行でプレースホルダを書いていたが、現在はタスク名を空文字で出力する
                writer.writerow([i, "", "", ""])
            else:
                for it in day_tasks:
                    writer.writerow([i, it["name"], it["assigned"], f"{it['time']:.2f}"])
        writer.writerow([])

        # (Remaining セクションは不要のため出力しない)
    

def _export_plan_txt(path, subject, day_capacities, tasks, total_needed, plan):
    # 人間が読みやすい形式でレポートを出力
    lines = []
    lines.append(f"科目: {subject}")
    lines.append(f"合計利用可能時間: {sum(day_capacities):.2f} 時間")
    lines.append(f"必要な総学習時間: {total_needed:.2f} 時間")
    lines.append(f"学習日数: {len(day_capacities)}")
    lines.append("="*40)
    lines.append("")
    lines.append("各日の利用可能時間:")
    for i, h in enumerate(day_capacities, start=1):
        lines.append(f"  Day {i}: {h:.2f} 時間")
    lines.append("")
    if total_needed <= sum(day_capacities):
        lines.append("すべてのタスクを完了するための十分な時間があります。\n")
    else:
        lines.append("注意: 利用可能時間より必要時間が多いです。計画を調整してください。\n")

    for i, day_tasks in enumerate(plan, start=1):
        lines.append(f"Day {i}:")
        if not day_tasks:
            # 空日の表示はプレースホルダを出さず、タスク行を出力しない
            pass
        else:
            for it in day_tasks:
                lines.append(f"  - {it['name']} を {it['assigned']} 問（合計 {it['time']:.2f} 時間）")
        lines.append("")

    remaining = [t for t in tasks if t["remaining"] > 0]
    if remaining:
        lines.append("割り当て後に残ったタスク:")
        for t in remaining:
            est = t["remaining"] * t["time_per_item"] * t["difficulty"]
            lines.append(f"  - {t['name']}: 残り {t['remaining']} 問（推定 {est:.2f} 時間）")
        lines.append('\n利用可能時間内に収めるには、問題数を減らすか、1問あたりの時間/難易度を見直してください。')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def prompt_and_save(subject, day_capacities, plan, tasks, total_needed):
    # 自動で CSV のみを plans フォルダーに保存する
    plans_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'plans'))
    os.makedirs(plans_dir, exist_ok=True)
    # ユーザーにファイル名を入力してもらう（拡張子不要）。空なら自動生成。
    user_name = input("保存するファイル名を入力してください（拡張子なし、Enterで自動生成）: ").strip()
    if user_name == "":
        basename = f"study_plan_{subject}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    else:
        # サニタイズ: 基本的にファイル名に使えない文字を除去
        bad = set(list('/\\:*?"<>|'))
        safe = ''.join(ch for ch in user_name if ch not in bad)
        if not safe.lower().endswith('.csv'):
            safe = safe + '.csv'
        basename = safe

    path = os.path.join(plans_dir, basename)
    # 上書き確認
    if os.path.exists(path):
        ans = input(f"{path} は既に存在します。上書きしますか？(y/n): ").strip().lower()
        if ans != 'y':
            print("保存をキャンセルしました。")
            return

    _export_plan_csv(path, subject, day_capacities, tasks, total_needed, plan)
    print(f"プランを保存しました: {path}")


def main():
    subject, day_capacities, total_available, tasks = collect_inputs()
    total_needed = compute_total_time(tasks)
    plan = allocate_by_priority(day_capacities, tasks)
    print_plan(subject, total_available, day_capacities, tasks, total_needed, plan)
    # 生成したプランを保存するか確認（テキストレポートも自動で作成されます）
    prompt_and_save(subject, day_capacities, plan, tasks, total_needed)


if __name__ == '__main__':
    main()

