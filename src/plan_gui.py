"""簡易 GUI (tkinter) - 新規プラン作成と既存 CSV からの更新 (再計画)

使い方:
    python src/plan_gui.py

注意: この GUI は `first_study_plan.py` と `done_task.py` の関数を動的にロードして利用します。
"""
import os
import csv
import importlib.util
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


SRC_DIR = os.path.dirname(__file__)
PLANS_DIR = os.path.abspath(os.path.join(SRC_DIR, '..', 'plans'))
os.makedirs(PLANS_DIR, exist_ok=True)


def load_module(name, filename):
    path = os.path.join(SRC_DIR, filename)
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


first_mod = load_module('first_study_plan', 'first_study_plan.py')
done_mod = load_module('done_task', 'done_task.py')


class PlannerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('学習プラン GUI')
        self.geometry('1000x700')

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)

        self.frame_new = ttk.Frame(nb)
        self.frame_update = ttk.Frame(nb)
        nb.add(self.frame_new, text='新規プラン')
        nb.add(self.frame_update, text='CSVから更新')

        self._build_new_tab()
        self._build_update_tab()

    def _build_new_tab(self):
        frm = self.frame_new

        left = ttk.Frame(frm)
        right = ttk.Frame(frm)
        left.pack(side='left', fill='y', padx=8, pady=8)
        right.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        # 科目 / 日付 / 共通時間
        ttk.Label(left, text='科目').pack(anchor='w')
        self.entry_subject = ttk.Entry(left)
        self.entry_subject.pack(fill='x')

        ttk.Label(left, text='開始日 (YYYY-MM-DD)').pack(anchor='w')
        self.entry_start = ttk.Entry(left)
        self.entry_start.pack(fill='x')

        ttk.Label(left, text='テスト日 (YYYY-MM-DD、任意)').pack(anchor='w')
        self.entry_test = ttk.Entry(left)
        self.entry_test.pack(fill='x')

        ttk.Label(left, text='1問あたり共通時間 (時間)').pack(anchor='w')
        self.entry_time_per = ttk.Entry(left)
        self.entry_time_per.pack(fill='x')

        ttk.Label(left, text='日ごとの利用可能時間 (カンマ区切り)').pack(anchor='w')
        self.text_day_caps = tk.Text(left, height=4)
        self.text_day_caps.pack(fill='x')

        ttk.Label(left, text='タスク (1行1件: 名前,合計問題数,優先順位,問題コスト)').pack(anchor='w')
        self.text_tasks = tk.Text(left, height=8)
        self.text_tasks.pack(fill='x')

        ttk.Button(left, text='プリセット読み込み', command=self._load_presets).pack(fill='x', pady=4)
        ttk.Button(left, text='プラン生成', command=self._generate_plan).pack(fill='x')
        ttk.Button(left, text='プラン保存 (CSV)', command=self._save_generated_plan).pack(fill='x', pady=4)

        # 右側: プラン出力
        ttk.Label(right, text='プラン出力').pack(anchor='w')
        self.txt_out = scrolledtext.ScrolledText(right)
        self.txt_out.pack(fill='both', expand=True)

        # internal
        self.generated = None
        self.generated_meta = None

    def _load_presets(self):
        if not first_mod:
            messagebox.showerror('エラー', 'first_study_plan.py が見つかりません')
            return
        # populate entries from module presets if available
        try:
            subj = getattr(first_mod, 'SUBJECT_PRESET', '')
            start = getattr(first_mod, 'START_DATE_PRESET', '')
            test = getattr(first_mod, 'TEST_DATE_PRESET', '')
            caps = getattr(first_mod, 'DAY_CAPACITIES_PRESET', [])
            tpi = getattr(first_mod, 'COMMON_TIME_PER_ITEM_PRESET', '')
            tasks = getattr(first_mod, 'TASKS_PRESET', [])
        except Exception:
            messagebox.showwarning('警告', 'プリセット読み込みに失敗しました')
            return
        self.entry_subject.delete(0, 'end'); self.entry_subject.insert(0, str(subj))
        self.entry_start.delete(0, 'end'); self.entry_start.insert(0, str(start) if start else '')
        self.entry_test.delete(0, 'end'); self.entry_test.insert(0, str(test) if test else '')
        self.entry_time_per.delete(0, 'end'); self.entry_time_per.insert(0, str(tpi))
        self.text_day_caps.delete('1.0', 'end'); self.text_day_caps.insert('1.0', ','.join(str(x) for x in caps))
        self.text_tasks.delete('1.0', 'end')
        for t in tasks:
            line = f"{t.get('name')},{t.get('total')},{t.get('priority')},{t.get('difficulty')}\n"
            self.text_tasks.insert('end', line)

    def _parse_inputs(self):
        subject = self.entry_subject.get().strip()
        start_date = self.entry_start.get().strip() or None
        test_date = self.entry_test.get().strip() or None
        try:
            time_per = float(self.entry_time_per.get().strip())
        except Exception:
            time_per = 0.0
        caps_s = self.text_day_caps.get('1.0', 'end').strip()
        day_caps = []
        if caps_s:
            for part in caps_s.replace('\n',',').split(','):
                part = part.strip()
                if not part: continue
                try:
                    day_caps.append(float(part))
                except Exception:
                    pass
        tasks = []
        for line in self.text_tasks.get('1.0','end').splitlines():
            if not line.strip(): continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
            name, total, priority, difficulty = parts[0], int(parts[1]), int(parts[2]), float(parts[3])
            tasks.append({'name': name, 'remaining': total, 'total': total, 'time_per_item': time_per, 'difficulty': difficulty, 'priority': priority})
        return subject, start_date, test_date, day_caps, tasks

    def _generate_plan(self):
        subject, start_date, test_date, day_caps, tasks = self._parse_inputs()
        if not tasks or not day_caps:
            messagebox.showwarning('警告', '日数とタスクを入力してください')
            return
        # use allocate_by_priority from first_mod if present
        if first_mod and hasattr(first_mod, 'allocate_by_priority'):
            # copy tasks for mutation
            import copy
            tasks_copy = copy.deepcopy(tasks)
            plan = first_mod.allocate_by_priority(day_caps, tasks_copy)
            total_needed = sum(t['total'] * t['time_per_item'] * t.get('difficulty',1.0) for t in tasks)
        else:
            messagebox.showerror('エラー', '割当関数が見つかりません')
            return

        # 割り当て後、残タスクがある場合は警告を出す
        total_assigned = {}
        for day_tasks in plan:
            for task in day_tasks:
                task_name = task['name']
                total_assigned[task_name] = total_assigned.get(task_name, 0) + task['assigned']
        
        unfinished_tasks = []
        for t in tasks:
            assigned_count = total_assigned.get(t['name'], 0)
            if assigned_count < t['total']:
                remaining_count = t['total'] - assigned_count
                unfinished_tasks.append(f"  {t['name']}: {remaining_count}問が未割当")
        
        if unfinished_tasks:
            warning_msg = "⚠️ 警告: 時間内にすべてのタスクを割り当てられませんでした。\n\n"
            warning_msg += "未割当のタスク:\n" + '\n'.join(unfinished_tasks)
            warning_msg += "\n\n各日の勉強時間を増やすか、タスクの優先度・難易度を調整してください。"
            messagebox.showwarning('時間不足', warning_msg)

        # show
        self.txt_out.delete('1.0','end')
        self.txt_out.insert('end', f"科目: {subject}\n開始: {start_date}\nテスト: {test_date}\n\n")
        # show (original line-by-line per day)
        self.generated = plan
        self.generated_meta = {'subject': subject, 'start_date': start_date, 'test_date': test_date, 'day_caps': day_caps, 'tasks': tasks, 'total_needed': total_needed}
        self.txt_out.delete('1.0','end')
        self.txt_out.insert('end', f"科目: {subject}\n開始: {start_date}\nテスト: {test_date}\n\n")
        for i, day_tasks in enumerate(plan, start=1):
            label = f"Day {i}"
            if start_date:
                try:
                    base = datetime.fromisoformat(start_date).date()
                    day_date = base + timedelta(days=(i-1))
                    label += f" ({day_date.month}/{day_date.day})"
                except Exception:
                    pass
            self.txt_out.insert('end', f"{label}:\n")
            if not day_tasks:
                # 空日の表示では「休憩」のプレースホルダを出さず、何も書かない
                pass
            else:
                for it in day_tasks:
                    self.txt_out.insert('end', f"  - {it['name']} を {it['assigned']} 問 合計 {it['time']:.2f} 時間\n")
            self.txt_out.insert('end','\n')

    def _save_generated_plan(self):
        if not self.generated or not self.generated_meta:
            messagebox.showwarning('警告', '先にプランを生成してください')
            return
        fname = filedialog.asksaveasfilename(initialdir=PLANS_DIR, defaultextension='.csv', filetypes=[('CSVファイル','*.csv')])
        if not fname:
            return
        # write CSV similar to first_study_plan format, include start_date/test_date
        meta = self.generated_meta
        plan = self.generated
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['subject', meta['subject']])
            writer.writerow(['generated_at', datetime.now().isoformat()])
            writer.writerow(['total_available', f"{sum(meta['day_caps']):.2f}"])
            writer.writerow(['total_needed', f"{meta['total_needed']:.2f}"])
            if meta.get('start_date'):
                writer.writerow(['start_date', meta['start_date']])
            if meta.get('test_date'):
                writer.writerow(['test_date', meta['test_date']])
            writer.writerow([])
            writer.writerow(['Day Capacities'])
            writer.writerow(['Day','AvailableHours'])
            for i,h in enumerate(meta['day_caps'], start=1):
                writer.writerow([i, f"{h:.2f}"])
            writer.writerow([])
            writer.writerow(['Plan'])
            writer.writerow(['Day','Task','Assigned','Time(hours)'])
            for i, day_tasks in enumerate(plan, start=1):
                if not day_tasks:
                    # 割当がない日はタスク名を空文字で CSV に出力する
                    writer.writerow([i, '', '', ''])
                else:
                    for it in day_tasks:
                        writer.writerow([i, it['name'], it['assigned'], f"{it['time']:.2f}"])
        messagebox.showinfo('保存完了', f'プランを保存しました: {fname}')

    # -- update tab
    def _build_update_tab(self):
        frm = self.frame_update
        top = ttk.Frame(frm)
        top.pack(fill='x', padx=8, pady=8)
        ttk.Button(top, text='CSV読み込み', command=self._load_csv_for_update).pack(side='left')
        ttk.Label(top, text='完了した日 (Day#)').pack(side='left', padx=6)
        self.entry_today = ttk.Entry(top, width=6)
        self.entry_today.pack(side='left')
        ttk.Button(top, text='完了を適用して再計画', command=self._apply_today_replan).pack(side='left', padx=6)

        self.txt_update = scrolledtext.ScrolledText(frm)
        self.txt_update.pack(fill='both', expand=True, padx=8, pady=8)
        # internal
        self.loaded_meta = None
        self.loaded_plan_rows = None

    def _load_csv_for_update(self):
        fpath = filedialog.askopenfilename(initialdir=PLANS_DIR, filetypes=[('CSVファイル','*.csv')])
        if not fpath:
            return
        # use done_task.load_plan_csv if available
        plan_data = None
        if done_mod and hasattr(done_mod, 'load_plan_csv'):
            plan_data = done_mod.load_plan_csv(fpath)
        else:
            # simple loader
            with open(fpath, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = [r for r in reader]
            # minimal parse: reuse code from done_task (lightweight)
            i=0; meta={}
            while i < len(rows) and rows[i]:
                r=rows[i]
                if len(r)>=2: meta[r[0]]=r[1]
                i+=1
            while i < len(rows) and not rows[i]: i+=1
            day_caps=[]
            if i < len(rows) and rows[i] and rows[i][0].strip()=='Day Capacities':
                i+=2
                # 同様に Day 列は絶対番号の可能性があるため辞書経由で整形する
                tmp = {}
                max_day = 0
                while i < len(rows) and rows[i]:
                    try:
                        dn = int(rows[i][0])
                        h = float(rows[i][1])
                        tmp[dn] = h
                        if dn > max_day: max_day = dn
                    except Exception:
                        pass
                    i+=1
                if max_day > 0:
                    day_caps = [0.0] * max_day
                    for dn, h in tmp.items():
                        if 1 <= dn <= max_day:
                            day_caps[dn-1] = h
            while i < len(rows) and not rows[i]: i+=1
            plan_rows=[]
            if i < len(rows) and rows[i] and rows[i][0].strip()=='Plan':
                i+=2
                while i < len(rows) and rows[i]:
                    r=rows[i]
                    try: day=int(r[0])
                    except: i+=1; continue
                    name=r[1]; assigned=0
                    try: assigned=int(r[2]) if r[2] else 0
                    except: assigned=0
                    timeh=0.0
                    try: timeh=float(r[3]) if r[3] else 0.0
                    except: timeh=0.0
                    plan_rows.append({'day':day,'name':name,'assigned':assigned,'time':timeh})
                    i+=1
            plan_data={'meta':meta,'day_capacities':day_caps,'plan_rows':plan_rows}

        self.loaded_meta = plan_data['meta']
        self.loaded_plan_rows = plan_data['plan_rows']
        # store day capacities as well for later saving/再計画保存時に利用
        self.loaded_day_caps = plan_data.get('day_capacities', [])
        # print summary
        self.txt_update.delete('1.0','end')
        self.txt_update.insert('end', f"読み込み: {os.path.basename(fpath)}\nメタ情報: {self.loaded_meta}\n\n")
        
        # 読み込まれた全データをDay別に表示
        days_data = {}
        for r in self.loaded_plan_rows:
            if not str(r.get('name','')).strip(): continue
            day = r.get('day', 0)
            if day not in days_data:
                days_data[day] = []
            days_data[day].append(f"{r['name']} {r['assigned']}問")
        
        self.txt_update.insert('end', "読み込まれたデータ（Day別）:\n")
        for day in sorted(days_data.keys()):
            tasks_str = ', '.join(days_data[day])
            self.txt_update.insert('end', f"  Day {day}: {tasks_str}\n")
        self.txt_update.insert('end', "\n")
        
        # タスク一覧を作る
        tasks_info = {}
        for r in self.loaded_plan_rows:
            # 空文字のタスク名行は集計対象外
            if not str(r.get('name','')).strip(): continue
            if r['name'] not in tasks_info: tasks_info[r['name']]={'total':0,'today':0,'prev':0}
            tasks_info[r['name']]['total'] += r['assigned']
        for name,info in tasks_info.items():
            self.txt_update.insert('end', f"{name}: 合計割当 {info['total']}\n")

    def _apply_today_replan(self):
        if not self.loaded_plan_rows:
            messagebox.showwarning('警告','まずCSVを読み込んでください')
            return
        try:
            today = int(self.entry_today.get().strip() or '1')
        except Exception:
            today = 1
        # aggregate tasks
        tasks = {}
        for r in self.loaded_plan_rows:
            # 空文字のタスク名行は集計対象外
            raw_name = r.get('name', '')
            if not str(raw_name).strip(): continue
            # タスク名を正規化してキーとして使う（空白を統一）
            n_key = str(raw_name).strip()
            info = tasks.setdefault(n_key, {'total_assigned':0, 'time_per_item_samples':[], 'first_day':r['day']})
            info['total_assigned'] += r['assigned']
            if r['assigned']>0:
                info['time_per_item_samples'].append(r['time']/r['assigned'] if r['assigned'] else 0)
            info['first_day'] = min(info['first_day'], r['day'])

        # prompt user for done_today values via simple dialog loop
        # ダイアログの提示順を安定させるため、明示的に優先度（first_day）→名前順でソートして表示する
        ordered = sorted(tasks.items(), key=lambda kv: (kv[1].get('first_day', 0), kv[0]))
        done_today = {}
        for name, info in ordered:
            # name は既に正規化済み（tasks 辞書作成時に strip 済み）
            prev = sum(int(r.get('assigned', 0)) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and int(r.get('day', 0)) < today)
            today_assigned = sum(int(r.get('assigned', 0)) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and int(r.get('day', 0)) == today)
            future_assigned = sum(int(r.get('assigned', 0)) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and int(r.get('day', 0)) > today)
            
            # デフォルトは今日の計画数（全部やった想定）
            suggested = today_assigned
            if suggested < 0:
                suggested = 0
            
            # プロンプトメッセージ
            if today_assigned > 0:
                prompt = f"{name}: Day {today}の計画={today_assigned}問 -> 実際に完了した数 (デフォルト {suggested}): "
            else:
                # 計画外のタスク（今日の計画=0だが、全体には存在する）
                prompt = f"{name}: Day {today}の計画=0問（計画外）-> 実際に完了した数があれば入力 (デフォルト 0): "
            
            s = tk.simpledialog.askstring('完了数入力', prompt)
            if s is None or s.strip() == '':
                done = int(suggested)
            else:
                try:
                    done = int(s.strip())
                except Exception:
                    done = 0
            
            # 入力値のバリデーション: 0以上、全体の残り数以下
            total_remaining = info['total_assigned'] - prev
            if done < 0:
                done = 0
            if done > total_remaining:
                # 入力が残り総数より大きい場合は警告して上限に合わせる
                messagebox.showwarning('入力エラー', f'{name}の完了数が残り総数({total_remaining}問)を超えています。{total_remaining}問に調整します。')
                done = total_remaining
            
            # done_today のキーとして正規化済みの name を使う
            done_today[name] = done

        # デバッグ出力は next_caps（再計画ウィンドウ）が分かってから出力するため、ここでは出さない

        # 次の日の利用可能時間を入力してもらう（1日分のみ）
        # それ以降の日は元CSVの day_capacities を使用
        s = tk.simpledialog.askstring('次の日入力', f'次の日（Day {today+1}）の利用可能時間を入力してください（例:3）:')
        if s is None: return
        try:
            next_day_cap = float(s.strip())
        except Exception:
            messagebox.showwarning('警告', f'数値を入力してください。入力値: "{s}"')
            return
        
        # 元CSVの day_capacities から次の日以降を取得
        orig_caps = getattr(self, 'loaded_day_caps', []) or []
        # next_caps = [次の日の入力値] + [元CSVの残りの日]
        next_caps = [next_day_cap]
        if today < len(orig_caps):
            # 元CSVの today+1 以降の容量を追加
            next_caps.extend(orig_caps[today+1:])
        
        self.txt_update.insert('end', f"[入力確認] 次の日（Day {today+1}）: {next_day_cap} 時間\n")
        self.txt_update.insert('end', f"[再計画範囲] Day {today+1}～{today+len(next_caps)}: {next_caps}\n\n")

        # cutoff_day を確定（today の次の日から next_caps の期間を再計画）
        cutoff_day = today + len(next_caps)

        # --- デバッグ出力: ユーザー入力とウィンドウ内の差分を表示して確認できるようにする ---
        debug_lines = [f"デバッグ: today={today}, cutoff_day={cutoff_day}, next_caps長={len(next_caps)}"]
        debug_lines.append("完了数サマリ（タスク名 / 過去+今日の割当 / 今日の計画 / 入力完了 / 未来の割当 / 残り）:")
        for name, info in ordered:
            # name は既に正規化済み
            # 過去+今日: today 以前（today を含む）- これらは固定
            past_and_today_rows = [(r.get('day'), r.get('assigned')) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and int(r.get('day', 0)) <= today]
            past_and_today = sum(int(assigned) for day, assigned in past_and_today_rows)
            # 今日の計画: today の割当
            today_plan = sum(int(r.get('assigned', 0)) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and int(r.get('day', 0)) == today)
            # 再計画ウィンドウ（未来）: today より後から cutoff_day まで
            future_rows = [(r.get('day'), r.get('assigned')) for r in self.loaded_plan_rows if str(r.get('name', '')).strip() == name and today < int(r.get('day', 0)) <= cutoff_day]
            future_plan = sum(int(assigned) for day, assigned in future_rows)
            done = done_today.get(name, 0)  # 正規化済みキーで取得
            # 残り計算: (今日の計画 + 未来) - 今日の完了
            # 計画外完了の場合、未来から差し引く
            rem = today_plan + future_plan - done
            if rem < 0: rem = 0
            today_remaining = max(0, today_plan - done)
            # 計画外完了の検出
            extra_msg = ""
            if done > today_plan:
                extra_msg = f" [計画外+{done - today_plan}]"
            debug_lines.append(f"  {name} / 過去+今日={past_and_today} / 今日計画={today_plan} / 入力完了={done}{extra_msg} / 今日残り={today_remaining} / 未来={future_plan} / 残り合計={rem}")
        # GUI の出力欄に表示
        self.txt_update.insert('end', '\n'.join(debug_lines) + '\n\n')

        # build remaining tasks: (今日の計画 + 未来の割当) - 完了数 を再計画する
        # ユーザーが入力した今日の完了数を差し引く。これにより、完了数は入力したタスク内でのみ反映され、
        # 他タスクへ影響が出ないようにする。計画外完了の場合、未来の割当から差し引く。
        remaining_tasks=[]
        for name,info in tasks.items():
            # name は既に正規化済み（tasks 辞書作成時に strip 済み）
            # 今日の計画: today の割当
            today_plan = sum(r['assigned'] for r in self.loaded_plan_rows if str(r.get('name','')).strip()==name and r['day']==today)
            # 未来の割当: today より後
            future_plan = sum(r['assigned'] for r in self.loaded_plan_rows if str(r.get('name','')).strip()==name and today < r['day'] <= cutoff_day)
            # ユーザー入力分はそのタスク内で差し引く（正規化済みキーで取得）
            done = done_today.get(name, 0)
            # 残り = (今日の計画 + 未来の割当) - 完了数
            rem = today_plan + future_plan - done
            if rem < 0: rem = 0
            tpi = (sum(info['time_per_item_samples'])/len(info['time_per_item_samples'])) if info['time_per_item_samples'] else 1.0
            remaining_tasks.append({'name':name,'remaining':int(rem),'time_per_item':float(tpi),'difficulty':1.0,'priority':int(info['first_day'])})

        # allocate using first_mod.allocate_by_priority
        tasks_alloc = []
        for t in remaining_tasks:
            tasks_alloc.append({'name':t['name'],'remaining':t['remaining'],'total':t['remaining'],'time_per_item':t['time_per_item'],'difficulty':t['difficulty'],'priority':t['priority']})
        if first_mod and hasattr(first_mod, 'allocate_by_priority'):
            plan = first_mod.allocate_by_priority(next_caps, tasks_alloc)
        else:
            messagebox.showerror('エラー','割当関数が見つかりません')
            return

        # 割り当て後、残タスクがある場合は警告を出す
        total_assigned = {}
        for day_tasks in plan:
            for task in day_tasks:
                task_name = task['name']
                total_assigned[task_name] = total_assigned.get(task_name, 0) + task['assigned']
        
        unfinished_tasks = []
        for t in tasks_alloc:
            assigned_count = total_assigned.get(t['name'], 0)
            if assigned_count < t['remaining']:
                remaining_count = t['remaining'] - assigned_count
                unfinished_tasks.append(f"  {t['name']}: {remaining_count}問が未割当")
        
        if unfinished_tasks:
            warning_msg = "⚠️ 警告: 時間内にすべてのタスクを割り当てられませんでした。\n\n"
            warning_msg += "未割当のタスク:\n" + '\n'.join(unfinished_tasks)
            warning_msg += "\n\n各日の勉強時間を増やすか、タスクの優先度・難易度を調整してください。"
            self.txt_update.insert('end', '\n' + warning_msg + '\n\n')
            messagebox.showwarning('時間不足', warning_msg)

        # render replan + remaining original future days in calendar view
        try:
            if self.loaded_meta.get('start_date'):
                base_date = datetime.fromisoformat(self.loaded_meta.get('start_date')).date()
                # 再計画は today の次の日から始まる（today は完了済み）
                start_day = today + 1
                new_start = (base_date + timedelta(days=(today))).isoformat()
            else:
                new_start = None
                start_day = today + 1
        except Exception:
            new_start = None
            start_day = today + 1

        header_meta = (self.loaded_meta.get('subject','(無題)'), new_start or self.loaded_meta.get('start_date'), self.loaded_meta.get('test_date'))

        # collect future days from loaded_plan_rows where day > cutoff_day and append after replan
        cutoff_day = today + len(next_caps)
        future_days_map = {}
        max_future_day = cutoff_day
        for r in self.loaded_plan_rows:
            try:
                d = int(r.get('day', 0))
            except Exception:
                continue
            if d > cutoff_day:
                max_future_day = max(max_future_day, d)
                future_days_map.setdefault(d, []).append({'name': r.get('name'), 'assigned': int(r.get('assigned',0)), 'time': float(r.get('time',0.0))})

        future_plan = []
        if future_days_map:
            for daynum in range(cutoff_day+1, max_future_day+1):
                day_tasks = future_days_map.get(daynum, [])
                # 空のタスク名（以前の '(休憩/学習無し)' を含む）を除外する
                filtered = [t for t in day_tasks if t.get('name') and t.get('name').strip() != '']
                if filtered:
                    conv = [{'name': t['name'], 'assigned': t['assigned'], 'time': t['time']} for t in filtered]
                else:
                    conv = []
                future_plan.append(conv)

        combined_plan = []
        combined_plan.extend(plan)
        if future_plan:
            combined_plan.extend(future_plan)

        # print combined plan in original (per-day) format
        # デバッグサマリは既に表示済みなので、削除せずに追記する
        self.txt_update.insert('end', f"\n再計画（開始 Day {start_day}）:\n\n")
        # base date for label calculation
        base_for_print = None
        if new_start:
            try:
                base_for_print = datetime.fromisoformat(new_start).date()
            except Exception:
                base_for_print = None
        for idx, day_tasks in enumerate(combined_plan, start=start_day):
            label = f"Day {idx}"
            if base_for_print:
                try:
                    d = base_for_print + timedelta(days=(idx - start_day))
                    label += f" ({d.month}/{d.day})"
                except Exception:
                    pass
            self.txt_update.insert('end', f"{label}:\n")
            if not day_tasks:
                # 空日はプレースホルダを出さない
                pass
            else:
                for it in day_tasks:
                    self.txt_update.insert('end', f"  - {it['name']} を {it['assigned']} 問 合計 {it['time']:.2f} 時間\n")
            self.txt_update.insert('end','\n')

        # ask to save
        if messagebox.askyesno('保存確認','この再計画を保存しますか？'):
            fname = filedialog.asksaveasfilename(initialdir=PLANS_DIR, defaultextension='.csv', filetypes=[('CSVファイル','*.csv')])
            if fname:
                with open(fname,'w',newline='',encoding='utf-8') as f:
                    w = csv.writer(f)
                    # header meta
                    w.writerow(['subject', self.loaded_meta.get('subject','(無題)')])
                    w.writerow(['generated_at', datetime.now().isoformat()])

                    # Build full day capacities array: ensure we include original loaded days and any new days from combined_plan
                    orig_caps = getattr(self, 'loaded_day_caps', []) or []
                    combined_len = start_day + len(combined_plan) - 1
                    total_days = max(len(orig_caps), combined_len)
                    full_day_caps = [0.0] * total_days
                    for idx in range(total_days):
                        if idx < len(orig_caps):
                            full_day_caps[idx] = orig_caps[idx]
                        else:
                            full_day_caps[idx] = 0.0

                    total_available = sum(full_day_caps)
                    # total_needed: sum of hours in the combined_plan
                    combined_total_time = 0.0
                    for day_tasks in combined_plan:
                        for it in day_tasks:
                            combined_total_time += float(it.get('time', 0.0))

                    w.writerow(['total_available', f"{total_available:.2f}"])
                    w.writerow(['total_needed', f"{combined_total_time:.2f}"])

                    # preserve start_date/test_date if present; update start_date to the original start if available
                    try:
                        if self.loaded_meta.get('start_date'):
                            # keep original start_date
                            w.writerow(['start_date', self.loaded_meta.get('start_date')])
                    except Exception:
                        pass
                    if self.loaded_meta.get('test_date'):
                        w.writerow(['test_date', self.loaded_meta.get('test_date')])

                    w.writerow([])
                    w.writerow(['Day Capacities'])
                    w.writerow(['Day','AvailableHours'])
                    for i, h in enumerate(full_day_caps, start=1):
                        w.writerow([i, f"{h:.2f}"])

                    # Plan: write rows for day=1..total_days, combining past original rows and new combined_plan
                    w.writerow([])
                    w.writerow(['Plan'])
                    w.writerow(['Day','Task','Assigned','Time(hours)'])

                    # Build map of original plan rows by day
                    orig_map = {}
                    for r in self.loaded_plan_rows:
                        try:
                            d = int(r.get('day', 0))
                        except Exception:
                            continue
                        orig_map.setdefault(d, []).append(r)

                    for day in range(1, total_days+1):
                        if day <= today:
                            # past days and today (completed): write original rows (if any)
                            rows = orig_map.get(day, [])
                            if not rows:
                                w.writerow([day, '', '', ''])
                            else:
                                for rr in rows:
                                    name = rr.get('name','') or ''
                                    assigned = int(rr.get('assigned',0)) if rr.get('assigned', '')!='' else ''
                                    timeh = float(rr.get('time',0.0)) if rr.get('time', '')!='' else ''
                                    w.writerow([day, name, assigned, f"{timeh:.2f}" if timeh!='' else ''])
                        else:
                            # future/replanned days (after today)
                            if start_day <= day < start_day + len(combined_plan):
                                rel = day - start_day
                                day_tasks = combined_plan[rel]
                                if not day_tasks:
                                    w.writerow([day, '', '', ''])
                                else:
                                    for it in day_tasks:
                                        w.writerow([day, it.get('name',''), it.get('assigned',0), f"{it.get('time',0.0):.2f}"])
                            else:
                                # if original had tasks for this day, write them; otherwise empty
                                rows = orig_map.get(day, [])
                                if not rows:
                                    w.writerow([day, '', '', ''])
                                else:
                                    for rr in rows:
                                        name = rr.get('name','') or ''
                                        assigned = int(rr.get('assigned',0)) if rr.get('assigned', '')!='' else ''
                                        timeh = float(rr.get('time',0.0)) if rr.get('time', '')!='' else ''
                                        w.writerow([day, name, assigned, f"{timeh:.2f}" if timeh!='' else ''])
                messagebox.showinfo('保存完了', f'プランを保存しました: {fname}')


if __name__ == '__main__':
    app = PlannerGUI()
    app.mainloop()
