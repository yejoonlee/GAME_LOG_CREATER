import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta
from tqdm import tqdm
import random

def setup_environment(seed, output_dir, output_format):
    os.makedirs(os.path.join(output_dir, output_format), exist_ok=True)
    return os.path.join(output_dir, output_format)

def generate_new_users(day, uid_counter, lambda_per_hour, steps_per_day, start_date, initial_energy=30):
    SECONDS_IN_A_DAY = 86400
    date = start_date + timedelta(days=day)
    new_users = sum(np.random.poisson(10) for _ in range(steps_per_day))
    users = []
    for _ in range(new_users):
        random_seconds = np.random.randint(0, SECONDS_IN_A_DAY)
        event_time = date + timedelta(seconds=random_seconds)
        uid = f"U{uid_counter:06d}"
        users.append({
            'UID': uid,
            'JOIN_TIME': event_time,
            'LAST_ENERGY_UPDATE_TIME': event_time,
            'ENERGY': 30,
            'CURRENT_CHAPTER': 1,
            'HAS_JOINED': False,
            'ACTIVE': True,
            'retry_counts': {},
            'current_step': 0,
            'clear_bonus': 0.0,
            'left_date': None
        })
        uid_counter += 1
    return users, uid_counter

def calculate_clear_success(chapter, days_since_join, clear_bonus):
    if chapter <= 3:
        base_success = 0.999
    elif 4 <= chapter <= 14:
        base_success = 0.98 - (chapter - 1) * 0.03
        if chapter == 10:
            base_success -= 0.08
        base_success = max(base_success, 0.6)
    elif 15 <= chapter <= 24:
        base_success = 0.98 - (chapter - 1) * 0.04
        if chapter == 20:
            base_success -= 0.08
        base_success = max(base_success, 0.4)
    else:
        base_success = 0.45 - (chapter - 25) * 0.05
        base_success = max(base_success, 0.1)

    bonus = days_since_join * 0.02
    final_success = min(base_success + bonus + clear_bonus, 1.0)
    return final_success

def update_energy(user, current_time):
    minutes_since_last_update = (current_time - user['LAST_ENERGY_UPDATE_TIME']).total_seconds() / 60
    recovery_times = int(minutes_since_last_update // 60)
    if recovery_times > 0:
        user['ENERGY'] = min(user['ENERGY'] + recovery_times * 5, 30)
        user['LAST_ENERGY_UPDATE_TIME'] += timedelta(minutes=recovery_times * 60)

def apply_retention(user, today_date, retention_curve, default_retention):
    days_since_join = (today_date.date() - user['JOIN_TIME'].date()).days
    if days_since_join <= 0:
        return
    if days_since_join in retention_curve:
        retention_rate = retention_curve[days_since_join]
    else:
        retention_rate = default_retention
    if np.random.rand() > retention_rate:
        user['ACTIVE'] = False
        user['left_date'] = today_date

def get_scale_for_time(hour):
    if 3 <= hour <= 8:
        return 10800
    elif 9 <= hour <= 20:
        return 5400
    elif 21 <= hour <= 23:
        return 2700
    else:
        return 3600

def simulate_user_day(user, today_date, item_logs):
    login_logs = []
    game_logs = []

    if not user['ACTIVE']:
        return [], []

    session_times = []
    current_time = 0
    while current_time < 86400:
        hour = int(current_time // 3600)
        scale = get_scale_for_time(hour)
        interval = np.random.exponential(scale=scale)
        current_time += interval
        if current_time < 86400:
            session_times.append(current_time)

    session_times = sorted(session_times)

    for seconds_since_midnight in session_times:
        session_time = datetime.combine(today_date, datetime.min.time()) + timedelta(seconds=int(seconds_since_midnight))

        update_energy(user, session_time)

        days_since_join = (today_date.date() - user['JOIN_TIME'].date()).days

        if not user['HAS_JOINED'] and session_time >= user['JOIN_TIME']:
            login_logs.append({
                "LOGTM": user['JOIN_TIME'].strftime('%Y-%m-%d %H:%M:%S'),
                "DATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "UID": user['UID'],
                "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "CODE": 10000,
                "ENERGY": user['ENERGY']
            })
            user['HAS_JOINED'] = True

        if user['HAS_JOINED'] and session_time >= user['JOIN_TIME']:
            login_logs.append({
                "LOGTM": session_time.strftime('%Y-%m-%d %H:%M:%S'),
                "DATE": session_time.strftime('%Y-%m-%d'),
                "UID": user['UID'],
                "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "CODE": 10001,
                "ENERGY": user['ENERGY']
            })

            current_session_time = session_time

            while user['ENERGY'] >= 5:
                if np.random.rand() < 0.8:
                    delta_seconds = np.random.randint(10, 301)
                    current_session_time += timedelta(seconds=delta_seconds)
                    update_energy(user, current_session_time)

                    clear_chance = calculate_clear_success(user['CURRENT_CHAPTER'], days_since_join, user['clear_bonus'])
                    clear_result = np.random.rand() < clear_chance

                    game_logs.append({
                        "LOGTM": current_session_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "DATE": current_session_time.strftime('%Y-%m-%d'),
                        "UID": user['UID'],
                        "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                        "CODE": 50001,
                        "CHAPTER": user['CURRENT_CHAPTER'],
                        "ENERGY": {"USE": 5, "REMAIN": user['ENERGY'] - 5},
                        "CLEAR": clear_result
                    })

                    user['ENERGY'] -= 5

                    if clear_result:
                        user['CURRENT_CHAPTER'] = min(user['CURRENT_CHAPTER'] + 1, 30)
                        if user['CURRENT_CHAPTER'] - 1 in user['retry_counts']:
                            user['retry_counts'][user['CURRENT_CHAPTER'] - 1] = 0
                    else:
                        user['retry_counts'][user['CURRENT_CHAPTER']] = user['retry_counts'].get(user['CURRENT_CHAPTER'], 0) + 1

                        # 15회 이상 재도전 시 이탈
                        if user['retry_counts'][user['CURRENT_CHAPTER']] >= 15:
                            user['ACTIVE'] = False
                            user['left_date'] = today_date
                            break

                        # 3회 이상 재도전 시 구매 시도
                        if user['retry_counts'][user['CURRENT_CHAPTER']] >= 3:
                            if user['CURRENT_CHAPTER'] in [10, 20, 30]:
                                # 10, 20, 30챕터에서는 8% 확률로 STEP_SPECIAL 구매
                                if np.random.rand() < 0.08:
                                    item_logs.append({
                                        "LOGTM": current_session_time.strftime('%Y-%m-%d %H:%M:%S'),
                                        "DATE": current_session_time.strftime('%Y-%m-%d'),
                                        "UID": user['UID'],
                                        "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                                        "CODE": 20001,
                                        "NAME": "STEP_SPECIAL",
                                        "PRICE": 20000,
                                        "CHAPTER": user['CURRENT_CHAPTER']
                                    })
                                    user['clear_bonus'] += 0.07  # STEP_SPECIAL 구매 시 성공 확률 7% 증가
                            else:
                                # 그 외 챕터에서는 5% 확률로 STEP1, STEP2, STEP3 순서로 구매
                                if np.random.rand() < 0.05 and user['current_step'] < 3:
                                    step_info = {
                                        0: ("STEP1", 1000, 0.03),
                                        1: ("STEP2", 10000, 0.05),
                                        2: ("STEP3", 50000, 0.09)
                                    }
                                    name, price, bonus = step_info[user['current_step']]
                                    item_logs.append({
                                        "LOGTM": current_session_time.strftime('%Y-%m-%d %H:%M:%S'),
                                        "DATE": current_session_time.strftime('%Y-%m-%d'),
                                        "UID": user['UID'],
                                        "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                                        "CODE": 20001,
                                        "NAME": name,
                                        "PRICE": price,
                                        "CHAPTER": user['CURRENT_CHAPTER']
                                    })
                                    user['clear_bonus'] += bonus
                                    user['current_step'] += 1
                else:
                    break

    return login_logs, game_logs



def recover_users(all_users, today_date):
    for user in all_users:
        if not user['ACTIVE'] and user['left_date']:
            days_since_left = (today_date - user['left_date']).days
            if 1 <= days_since_left <= 7:
                if np.random.rand() < 0.05:
                    user['ACTIVE'] = True
                    user['retry_counts'] = {}
                    user['left_date'] = None

def save_daily_logs(login_logs, game_logs, item_logs, output_dir, date_str, output_format):
    login_df = pd.DataFrame(login_logs)
    game_df = pd.DataFrame(game_logs)
    item_df = pd.DataFrame(item_logs)

    date_dir = os.path.join(output_dir, date_str)
    os.makedirs(date_dir, exist_ok=True)

    login_path = os.path.join(date_dir, f'login_{date_str}.{output_format}')
    gamelog_path = os.path.join(date_dir, f'gamelog_{date_str}.{output_format}')
    itemlog_path = os.path.join(date_dir, f'item_{date_str}.{output_format}')

    if output_format == 'json':
        login_df.to_json(login_path, orient='records', lines=True, force_ascii=False)
        game_df.to_json(gamelog_path, orient='records', lines=True, force_ascii=False)
        item_df.to_json(itemlog_path, orient='records', lines=True, force_ascii=False)
    elif output_format == 'parquet':
        import pyarrow as pa
        import pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pandas(login_df), login_path)
        pq.write_table(pa.Table.from_pandas(game_df), gamelog_path)
        pq.write_table(pa.Table.from_pandas(item_df), itemlog_path)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

def run_simulation(start_date, days, output_dir, output_format='json', lambda_per_hour=2.5, steps_per_day=24, seed=42):
    np.random.seed(seed)
    random.seed(seed)

    output_dir = setup_environment(seed, output_dir, output_format)
    uid_counter = 1
    all_users = []


    retention_curve = {
        1: 0.4,
        2: 0.2,
        3: 0.15,
        4: 0.12,
        5: 0.10,
        6: 0.08,
        7: 0.05
    }
    default_retention = 0.03

    for day in tqdm(range(days), desc="Simulating daily logs"):
        today_date = start_date + timedelta(days=day)

        new_users, uid_counter = generate_new_users(day, uid_counter, lambda_per_hour, steps_per_day, start_date)
        all_users.extend(new_users)

        recover_users(all_users, today_date)

        login_logs = []
        game_logs = []
        item_logs = []

        for user in all_users:
            apply_retention(user, today_date, retention_curve, default_retention)
            today_login_logs, today_game_logs = simulate_user_day(user, today_date, item_logs)
            login_logs.extend(today_login_logs)
            game_logs.extend(today_game_logs)

        date_str = today_date.strftime('%Y%m%d')
        save_daily_logs(login_logs, game_logs, item_logs, output_dir, date_str, output_format)

    print(f"\n[INFO] 모든 로그가 '{output_dir}' 경로에 {output_format.upper()} 형식으로 저장되었습니다.")

def debug_simulate_user_day(user, today_date):
    login_logs = []
    game_logs = []
    item_logs = []

    if not user['ACTIVE']:
        print(f"[INFO] 유저 {user['UID']}는 비활성화 상태입니다.")
        return [], []

    session_times = []
    current_time = 0
    while current_time < 86400:
        hour = int(current_time // 3600)
        scale = get_scale_for_time(hour)
        interval = np.random.exponential(scale=scale)
        current_time += interval
        if current_time < 86400:
            session_times.append(current_time)

    session_times = sorted(session_times)

    print(f"[DEBUG] 생성된 세션 수: {len(session_times)}개")

    for seconds_since_midnight in session_times:
        session_time = datetime.combine(today_date, datetime.min.time()) + timedelta(seconds=int(seconds_since_midnight))

        update_energy(user, session_time)

        days_since_join = (today_date.date() - user['JOIN_TIME'].date()).days

        if not user['HAS_JOINED'] and session_time >= user['JOIN_TIME']:
            login_logs.append({
                "LOGTM": user['JOIN_TIME'].strftime('%Y-%m-%d %H:%M:%S'),
                "DATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "UID": user['UID'],
                "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "CODE": 10000,
                "ENERGY": user['ENERGY']
            })
            user['HAS_JOINED'] = True

        if user['HAS_JOINED'] and session_time >= user['JOIN_TIME']:
            login_logs.append({
                "LOGTM": session_time.strftime('%Y-%m-%d %H:%M:%S'),
                "DATE": session_time.strftime('%Y-%m-%d'),
                "UID": user['UID'],
                "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                "CODE": 10001,
                "ENERGY": user['ENERGY']
            })

            print(f"[DEBUG] 접속시간: {session_time}, 에너지: {user['ENERGY']}")

            current_session_time = session_time
            first_game = True

            while user['ENERGY'] >= 5:
                if first_game or np.random.rand() < 0.8:
                    first_game = False

                    delta_seconds = np.random.randint(10, 301)
                    current_session_time += timedelta(seconds=delta_seconds)
                    update_energy(user, current_session_time)

                    clear_chance = calculate_clear_success(user['CURRENT_CHAPTER'], days_since_join, user['clear_bonus'])
                    clear_result = np.random.rand() < clear_chance

                    game_logs.append({
                        "LOGTM": current_session_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "DATE": current_session_time.strftime('%Y-%m-%d'),
                        "UID": user['UID'],
                        "JOINDATE": user['JOIN_TIME'].strftime('%Y-%m-%d'),
                        "CODE": 50001,
                        "CHAPTER": user['CURRENT_CHAPTER'],
                        "ENERGY": {"USE": 5, "REMAIN": user['ENERGY'] - 5},
                        "CLEAR": clear_result
                    })

                    user['ENERGY'] -= 5

                    if clear_result:
                        user['CURRENT_CHAPTER'] = min(user['CURRENT_CHAPTER'] + 1, 30)
                        if user['CURRENT_CHAPTER'] - 1 in user['retry_counts']:
                            user['retry_counts'][user['CURRENT_CHAPTER'] - 1] = 0
                    else:
                        user['retry_counts'][user['CURRENT_CHAPTER']] = user['retry_counts'].get(user['CURRENT_CHAPTER'], 0) + 1

                        if user['retry_counts'][user['CURRENT_CHAPTER']] >= 15:
                            user['ACTIVE'] = False
                            user['left_date'] = today_date
                            break
                else:
                    break

    return login_logs, game_logs

if __name__ == "__main__":
    run_simulation(
        start_date=pd.to_datetime('2025-04-01'),
        days=10,
        output_dir='D:\\LOG CREATER\\results',
        output_format='json'
    )