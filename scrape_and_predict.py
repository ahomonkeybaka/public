#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
競馬予測システム - netkeibaスクレイピング版
出馬表と各馬の過去成績を取得し、勝ち馬を予測する
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import sys

# リクエスト設定
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
    'Connection': 'keep-alive',
}


@dataclass
class RaceResult:
    """過去レース結果"""
    date: str = ""
    course: str = ""
    race_name: str = ""
    distance: int = 0
    track_type: str = ""
    finish: int = 0
    total_horses: int = 0
    time: str = ""
    odds: float = 0
    popularity: int = 0
    weight: float = 0
    weight_diff: str = ""


@dataclass 
class Horse:
    """馬データ"""
    number: int = 0
    gate: int = 0
    name: str = ""
    sex: str = ""
    age: int = 0
    jockey: str = ""
    weight_carry: float = 0
    trainer: str = ""
    horse_weight: int = 0
    weight_diff: str = ""
    odds: float = 0
    popularity: int = 0
    horse_id: str = ""
    results: List[RaceResult] = field(default_factory=list)


@dataclass
class RaceInfo:
    """レース情報"""
    race_id: str = ""
    race_name: str = ""
    race_number: int = 0
    course: str = ""
    distance: int = 0
    track_type: str = ""
    track_condition: str = ""
    weather: str = ""
    date: str = ""
    start_time: str = ""


def get_base_url(race_id: str) -> str:
    """レースIDからベースURLを決定（JRA or 地方）"""
    # 地方競馬のコードは3桁目が4（例: 202542...）、JRAは0（例: 202508...）など
    if race_id[4] == '4':  # 地方競馬
        return "https://nar.netkeiba.com"
    else:  # JRA
        return "https://race.netkeiba.com"


def fetch_race_page(race_id: str) -> Optional[str]:
    """出馬表ページを取得"""
    base_url = get_base_url(race_id)
    url = f"{base_url}/race/shutuba.html?race_id={race_id}"
    print(f"出馬表を取得中: {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'euc-jp'
        
        if response.status_code == 200:
            print(f"  ✓ 取得成功 ({len(response.text)} bytes)")
            return response.text
        else:
            print(f"  ✗ エラー: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"  ✗ エラー: {e}")
        return None


def fetch_horse_page(horse_id: str) -> Optional[str]:
    """馬の成績ページを取得"""
    # 成績データは /horse/result/ から取得する
    url = f"https://db.netkeiba.com/horse/result/{horse_id}/"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.encoding = 'euc-jp'
        
        if response.status_code == 200:
            return response.text
        return None
    except:
        return None


def parse_race_page(html: str, race_id: str) -> Tuple[RaceInfo, List[Horse]]:
    """出馬表ページを解析"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # レース情報
    race_info = RaceInfo(race_id=race_id)
    
    # レース名
    race_name_elem = soup.select_one('.RaceName')
    if race_name_elem:
        race_info.race_name = race_name_elem.get_text(strip=True)
    
    # レースデータ（距離、コースなど）
    race_data01 = soup.select_one('.RaceData01')
    if race_data01:
        text = race_data01.get_text()
        
        # 距離
        dist_match = re.search(r'(\d{3,4})m', text)
        if dist_match:
            race_info.distance = int(dist_match.group(1))
        
        # コースタイプ
        if 'ダ' in text:
            race_info.track_type = 'ダート'
        elif '芝' in text:
            race_info.track_type = '芝'
        
        # 天候・馬場状態
        weather_match = re.search(r'天候:(\S+)', text)
        if weather_match:
            race_info.weather = weather_match.group(1)
        
        condition_match = re.search(r'(良|稍重|重|不良)', text)
        if condition_match:
            race_info.track_condition = condition_match.group(1)
    
    # 競馬場
    race_data02 = soup.select_one('.RaceData02')
    if race_data02:
        text = race_data02.get_text()
        # JRA
        for course_name in ['東京', '中山', '阪神', '京都', '中京', '新潟', '福島', '小倉', '札幌', '函館']:
            if course_name in text:
                race_info.course = course_name
                break
        # 地方
        if not race_info.course:
            for course_name in ['大井', '船橋', '川崎', '浦和', '門別', '園田', '姫路', '高知', '佐賀', '名古屋', '笠松', '金沢', '盛岡', '水沢']:
                if course_name in text:
                    race_info.course = course_name
                    break
    
    # 馬データを取得
    horses = []
    horse_rows = soup.select('tr.HorseList')
    
    for row in horse_rows:
        horse = Horse()
        
        # 枠番 - Waku1, Waku2, ... などのクラスを探す
        waku_cell = row.select_one('td[class*="Waku"]')
        if waku_cell:
            span = waku_cell.select_one('span')
            if span:
                try:
                    horse.gate = int(span.get_text(strip=True))
                except:
                    pass
            elif waku_cell.get_text(strip=True).isdigit():
                horse.gate = int(waku_cell.get_text(strip=True))
        
        # 馬番 - Umaban1, Umaban2, ... などのクラスを探す
        umaban_cell = row.select_one('td[class*="Umaban"]')
        if umaban_cell:
            text = umaban_cell.get_text(strip=True)
            if text.isdigit():
                horse.number = int(text)
        
        # 馬名とID - span.HorseName の中の a タグ
        horse_name_link = row.select_one('span.HorseName a')
        if horse_name_link:
            # title属性から馬名を取得（文字化け回避）
            horse.name = horse_name_link.get('title', '') or horse_name_link.get_text(strip=True)
            href = horse_name_link.get('href', '')
            id_match = re.search(r'horse/(\d+)', href)
            if id_match:
                horse.horse_id = id_match.group(1)
        
        # 性齢
        barei_cell = row.select_one('td.Barei')
        if barei_cell:
            text = barei_cell.get_text(strip=True)
            sex_match = re.search(r'(牡|牝|セ)', text)
            age_match = re.search(r'(\d+)', text)
            if sex_match:
                horse.sex = sex_match.group(1)
            if age_match:
                horse.age = int(age_match.group(1))
        
        # 斤量 - td 内のテキストから数字を取得
        cells = row.select('td')
        for cell in cells:
            text = cell.get_text(strip=True)
            # 斤量は通常50-60台の小数
            weight_match = re.match(r'^(\d{2}\.\d)$', text)
            if weight_match:
                horse.weight_carry = float(weight_match.group(1))
                break
        
        # 騎手
        jockey_cell = row.select_one('td.Jockey')
        if jockey_cell:
            jockey_link = jockey_cell.select_one('a')
            if jockey_link:
                horse.jockey = jockey_link.get_text(strip=True)
        
        # 調教師
        trainer_cell = row.select_one('td.Trainer')
        if trainer_cell:
            trainer_link = trainer_cell.select_one('a')
            if trainer_link:
                horse.trainer = trainer_link.get_text(strip=True)
        
        # オッズ - span#odds-1_XX の形式
        odds_span = row.select_one('td.Popular span[id^="odds-"]')
        if odds_span:
            try:
                odds_text = odds_span.get_text(strip=True)
                if odds_text != '---.-':
                    horse.odds = float(odds_text)
            except:
                pass
        
        # 人気
        ninki_cell = row.select_one('td.Popular_Ninki')
        if ninki_cell:
            text = ninki_cell.get_text(strip=True)
            if text.isdigit():
                horse.popularity = int(text)
        
        if horse.name and horse.number > 0:
            horses.append(horse)
    
    return race_info, horses


def parse_horse_history(html: str) -> List[RaceResult]:
    """馬の過去成績を解析"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    # 成績テーブルを取得
    table = soup.select_one('table.db_h_race_results')
    if not table:
        table = soup.select_one('table.nk_tb_common')
    
    if not table:
        return results
    
    # tbodyの中のtrを取得（ヘッダーを除く）
    tbody = table.select_one('tbody')
    if tbody:
        rows = tbody.select('tr')
    else:
        rows = table.select('tr')
    
    for row in rows:
        cells = row.select('td')
        if len(cells) < 15:
            continue
        
        result = RaceResult()
        
        try:
            # 列の構造（ヘッダーから推測）:
            # 0: 日付, 1: 開催, 2: 天気, 3: R, 4: レース名, 5: 映像, 
            # 6: 頭数, 7: 枠番, 8: 馬番, 9: オッズ, 10: 人気, 11: 着順,
            # 12: 騎手, 13: 斤量, 14: 距離, ...
            
            # 日付（0番目）
            date_link = cells[0].select_one('a')
            result.date = date_link.get_text(strip=True) if date_link else cells[0].get_text(strip=True)
            
            # 競馬場（1番目）
            course_link = cells[1].select_one('a')
            result.course = course_link.get_text(strip=True) if course_link else cells[1].get_text(strip=True)
            
            # レース名（4番目）
            race_link = cells[4].select_one('a')
            result.race_name = race_link.get_text(strip=True) if race_link else cells[4].get_text(strip=True)
            
            # 頭数（6番目）
            try:
                result.total_horses = int(cells[6].get_text(strip=True))
            except:
                result.total_horses = 0
            
            # 着順（11番目）
            finish_text = cells[11].get_text(strip=True)
            if finish_text.isdigit():
                result.finish = int(finish_text)
            else:
                continue  # 着順が数字でなければスキップ（中止など）
            
            # 距離・コースタイプ（14番目）
            dist_text = cells[14].get_text(strip=True)
            dist_match = re.search(r'([芝ダ障])(\d{3,4})', dist_text)
            if dist_match:
                result.track_type = 'ダート' if dist_match.group(1) == 'ダ' else '芝'
                result.distance = int(dist_match.group(2))
            
            # オッズ（9番目）
            try:
                odds_text = cells[9].get_text(strip=True)
                result.odds = float(odds_text)
            except:
                pass
            
            # 人気（10番目）
            try:
                pop_text = cells[10].get_text(strip=True)
                result.popularity = int(pop_text)
            except:
                pass
            
            results.append(result)
            
        except Exception as e:
            continue
    
    return results[:20]  # 最新20走まで


def calculate_score(horse: Horse, race_info: RaceInfo, all_horses: List[Horse]) -> Dict:
    """馬のスコアを計算"""
    score_details = {}
    total_score = 0
    
    results = horse.results
    
    # 1. 近走成績スコア (35%)
    recent_score = 50
    if results:
        weights = [0.35, 0.25, 0.2, 0.12, 0.08]
        weighted_sum = 0
        for i, r in enumerate(results[:5]):
            if i < len(weights):
                # 着順をスコア化 (1着=100, 以降減少)
                finish_score = max(0, 100 - (r.finish - 1) * 12)
                weighted_sum += finish_score * weights[i]
        recent_score = weighted_sum
    score_details['recent'] = recent_score
    total_score += recent_score * 0.35
    
    # 2. 勝率・複勝率 (15%)
    basic_score = 50
    if results:
        wins = sum(1 for r in results if r.finish == 1)
        places = sum(1 for r in results if r.finish <= 3)
        win_rate = wins / len(results)
        place_rate = places / len(results)
        basic_score = win_rate * 50 + place_rate * 50
    score_details['basic'] = basic_score
    total_score += basic_score * 0.15
    
    # 3. 距離適性 (12%)
    distance_score = 50
    if results and race_info.distance:
        same_dist = [r for r in results if abs(r.distance - race_info.distance) <= 100]
        if same_dist:
            places = sum(1 for r in same_dist if r.finish <= 3)
            distance_score = (places / len(same_dist)) * 100
    score_details['distance'] = distance_score
    total_score += distance_score * 0.12
    
    # 4. コース適性 (8%)
    course_score = 50
    if results and race_info.course:
        same_course = [r for r in results if race_info.course in r.course]
        if same_course:
            places = sum(1 for r in same_course if r.finish <= 3)
            course_score = (places / len(same_course)) * 100
    score_details['course'] = course_score
    total_score += course_score * 0.08
    
    # 5. 枠順 (8%)
    draw_score = 50
    total = len(all_horses)
    if horse.number and total > 0:
        position = (horse.number - 1) / max(total - 1, 1)
        # 内枠有利 (短距離ほど)
        inner_bias = 0.2 if race_info.distance <= 1400 else 0.1
        draw_score = (1 - position * inner_bias) * 100
    score_details['draw'] = draw_score
    total_score += draw_score * 0.08
    
    # 6. オッズ評価 (10%)
    odds_score = 50
    if horse.odds and horse.odds > 0:
        odds_score = max(0, 100 - math.log(horse.odds) * 18)
    score_details['odds'] = odds_score
    total_score += odds_score * 0.10
    
    # 7. 安定性 (7%)
    stability_score = 50
    if len(results) >= 3:
        finishes = [r.finish for r in results[:10]]
        import statistics
        std = statistics.stdev(finishes) if len(finishes) > 1 else 0
        stability_score = max(0, 100 - std * 12)
    score_details['stability'] = stability_score
    total_score += stability_score * 0.07
    
    # 8. 斤量 (5%)
    weight_score = 50
    weights = [h.weight_carry for h in all_horses if h.weight_carry > 0]
    if weights and horse.weight_carry:
        avg_weight = sum(weights) / len(weights)
        diff = horse.weight_carry - avg_weight
        weight_score = 50 - diff * 8
        weight_score = max(0, min(100, weight_score))
    score_details['weight'] = weight_score
    total_score += weight_score * 0.05
    
    return {
        'total': total_score,
        'details': score_details
    }


def predict(horses: List[Horse], race_info: RaceInfo) -> List[Dict]:
    """予測を実行"""
    predictions = []
    
    for horse in horses:
        score_data = calculate_score(horse, race_info, horses)
        predictions.append({
            'horse': horse,
            'score': score_data['total'],
            'details': score_data['details']
        })
    
    # スコアで降順ソート
    predictions.sort(key=lambda x: x['score'], reverse=True)
    
    # 正規化・勝率計算
    scores = [p['score'] for p in predictions]
    min_s, max_s = min(scores), max(scores)
    
    # Softmax で勝率推定
    temperature = 0.3
    exp_scores = []
    for p in predictions:
        norm = (p['score'] - min_s) / (max_s - min_s) if max_s > min_s else 0.5
        p['norm_score'] = norm
        exp_scores.append(math.exp(norm / temperature))
    
    total_exp = sum(exp_scores)
    for i, p in enumerate(predictions):
        p['win_prob'] = exp_scores[i] / total_exp
        p['rank'] = i + 1
        
        # 期待値
        if p['horse'].odds and p['horse'].odds > 0:
            p['expected_value'] = p['win_prob'] * p['horse'].odds
        else:
            p['expected_value'] = 0
    
    return predictions


def display_results(predictions: List[Dict], race_info: RaceInfo):
    """結果を表示"""
    sep = '=' * 90
    line = '-' * 90
    
    print(f"\n{sep}")
    print(f"  【予測結果】 {race_info.race_name}")
    print(sep)
    print(f"  競馬場: {race_info.course} | 距離: {race_info.distance}m ({race_info.track_type})")
    print(f"  馬場: {race_info.track_condition or '不明'} | 出走頭数: {len(predictions)}頭")
    print(line)
    
    # ランキング
    print("\n  【予測ランキング】\n")
    print("  順位  馬番  馬名             スコア   勝率    オッズ  期待値  分析")
    print("  " + "-" * 82)
    
    marks = ['◎', '○', '▲', '△', '△', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ']
    
    for p in predictions:
        h = p['horse']
        rank = p['rank']
        mark = marks[rank-1] if rank <= len(marks) else ' '
        
        # 分析コメント
        analysis = []
        d = p['details']
        if d['recent'] >= 70:
            analysis.append('近走◎')
        elif d['recent'] < 40:
            analysis.append('近走△')
        if d['distance'] >= 70:
            analysis.append('距離◎')
        if d['draw'] >= 60:
            analysis.append('枠○')
        
        analysis_str = '/'.join(analysis[:3]) if analysis else '-'
        
        odds_str = f"{h.odds:.1f}" if h.odds else "-"
        ev_str = f"{p['expected_value']:.2f}" if p['expected_value'] > 0 else "-"
        
        print(f"  {mark}{rank:<3} {h.number:>3}   {h.name:<14} {p['norm_score']:.3f}   {p['win_prob']*100:>5.1f}%  {odds_str:>6}  {ev_str:>6}  {analysis_str}")
    
    print("  " + "-" * 82)
    
    # 馬券推奨
    print(f"\n{sep}")
    print("  【馬券推奨】")
    print(sep)
    
    top = predictions[:5]
    print(f"\n  ◎本命: {top[0]['horse'].number}番 {top[0]['horse'].name} (勝率: {top[0]['win_prob']*100:.1f}%)")
    print(f"  ○対抗: {top[1]['horse'].number}番 {top[1]['horse'].name} (勝率: {top[1]['win_prob']*100:.1f}%)")
    print(f"  ▲単穴: {top[2]['horse'].number}番 {top[2]['horse'].name} (勝率: {top[2]['win_prob']*100:.1f}%)")
    print(f"  △連下: {top[3]['horse'].number}番, {top[4]['horse'].number}番")
    
    print(f"\n  【買い目】")
    print(f"  単勝: {top[0]['horse'].number}番")
    print(f"  馬連: {top[0]['horse'].number}-{top[1]['horse'].number}")
    print(f"  3連複: {top[0]['horse'].number}-{top[1]['horse'].number}-{top[2]['horse'].number}")
    print(f"  3連単: {top[0]['horse'].number}→{top[1]['horse'].number}→{top[2]['horse'].number}")
    
    # 期待値分析
    ev_sorted = sorted([p for p in predictions if p['expected_value'] > 0], 
                       key=lambda x: x['expected_value'], reverse=True)
    if ev_sorted:
        print(f"\n  【期待値上位】（穴馬候補）")
        for p in ev_sorted[:3]:
            h = p['horse']
            print(f"  ★ {h.number}番 {h.name}: 期待値 {p['expected_value']:.2f} (オッズ: {h.odds:.1f})")
    
    print(f"\n{sep}")
    print("  ※ 本予測は参考情報です。馬券購入は自己責任でお願いします。")
    print(sep)


def main():
    """メイン処理"""
    print("=" * 90)
    print("       競馬予測システム - netkeiba スクレイピング版")
    print("=" * 90)
    
    # レースID（コマンドライン引数または デフォルト）
    race_id = sys.argv[1] if len(sys.argv) > 1 else "202508040701"
    
    # 1. 出馬表を取得
    html = fetch_race_page(race_id)
    if not html:
        print("\n❌ 出馬表の取得に失敗しました")
        print("   debug_shutuba.html からの読み込みを試みます...")
        try:
            with open('debug_shutuba.html', 'r', encoding='utf-8') as f:
                html = f.read()
            print("   ✓ ローカルファイルを読み込みました")
        except:
            print("   ❌ ローカルファイルも見つかりません")
            return
    
    # 2. 出馬表を解析
    race_info, horses = parse_race_page(html, race_id)
    
    if not horses:
        print("\n❌ 馬データを取得できませんでした")
        return
    
    print(f"\n📊 レース情報:")
    print(f"   レース名: {race_info.race_name}")
    print(f"   競馬場: {race_info.course}")
    print(f"   距離: {race_info.distance}m {race_info.track_type}")
    print(f"   出走頭数: {len(horses)}頭")
    
    # 3. 各馬の過去成績を取得
    print(f"\n📈 各馬の過去成績を取得中...")
    for horse in horses:
        if horse.horse_id:
            print(f"   {horse.number}番 {horse.name}...", end=" ", flush=True)
            horse_html = fetch_horse_page(horse.horse_id)
            if horse_html:
                horse.results = parse_horse_history(horse_html)
                print(f"✓ ({len(horse.results)}走)")
            else:
                print("✗")
            time.sleep(0.3)  # サーバー負荷軽減
        else:
            print(f"   {horse.number}番 {horse.name}... (IDなし・新馬?)")
    
    # 4. 出走馬一覧
    print(f"\n📋 出走馬一覧:")
    for h in horses:
        recent = '-'.join(str(r.finish) for r in h.results[:3]) if h.results else '-'
        print(f"   {h.number:>2}番 {h.name:<12} {h.sex}{h.age} {h.jockey:<8} 斤量:{h.weight_carry}kg オッズ:{h.odds or '-':>5} 近走:{recent}")
    
    # 5. 予測実行
    print(f"\n🔮 予測モデルを実行中...")
    predictions = predict(horses, race_info)
    
    # 6. 結果表示
    display_results(predictions, race_info)


if __name__ == '__main__':
    main()
