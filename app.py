#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
競馬予測システム - Streamlit GUI版
Gemini-2.5-Pro AIによる高精度予測
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
import os
import pandas as pd

# ページ設定
st.set_page_config(
    page_title="競馬AI予測システム",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A5F;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .prediction-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        margin: 0.5rem 0;
    }
    .horse-rank-1 { background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); }
    .horse-rank-2 { background: linear-gradient(135deg, #C0C0C0 0%, #A0A0A0 100%); }
    .horse-rank-3 { background: linear-gradient(135deg, #CD7F32 0%, #8B4513 100%); }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

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
    """レースIDからベースURLを決定"""
    if len(race_id) > 4 and race_id[4] == '4':
        return "https://nar.netkeiba.com"
    else:
        return "https://race.netkeiba.com"


@st.cache_data(ttl=300)
def fetch_race_page(race_id: str) -> Optional[str]:
    """出馬表ページを取得"""
    base_url = get_base_url(race_id)
    url = f"{base_url}/race/shutuba.html?race_id={race_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'euc-jp'
        
        if response.status_code == 200:
            return response.text
        return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_horse_page(horse_id: str) -> Optional[str]:
    """馬の成績ページを取得"""
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
    
    race_info = RaceInfo(race_id=race_id)
    
    # レース名
    race_name_elem = soup.select_one('.RaceName')
    if race_name_elem:
        race_info.race_name = race_name_elem.get_text(strip=True)
    
    # レースデータ
    race_data01 = soup.select_one('.RaceData01')
    if race_data01:
        text = race_data01.get_text()
        
        dist_match = re.search(r'(\d{3,4})m', text)
        if dist_match:
            race_info.distance = int(dist_match.group(1))
        
        if 'ダ' in text:
            race_info.track_type = 'ダート'
        elif '芝' in text:
            race_info.track_type = '芝'
        
        condition_match = re.search(r'(良|稍重|重|不良)', text)
        if condition_match:
            race_info.track_condition = condition_match.group(1)
    
    # 競馬場
    race_data02 = soup.select_one('.RaceData02')
    if race_data02:
        text = race_data02.get_text()
        for course_name in ['東京', '中山', '阪神', '京都', '中京', '新潟', '福島', '小倉', '札幌', '函館',
                           '大井', '船橋', '川崎', '浦和', '門別', '園田', '姫路', '高知', '佐賀', '名古屋', '笠松', '金沢', '盛岡', '水沢']:
            if course_name in text:
                race_info.course = course_name
                break
    
    # 馬データを取得
    horses = []
    horse_rows = soup.select('tr.HorseList')
    
    for row in horse_rows:
        horse = Horse()
        
        # 枠番
        waku_cell = row.select_one('td[class*="Waku"]')
        if waku_cell:
            span = waku_cell.select_one('span')
            if span:
                try:
                    horse.gate = int(span.get_text(strip=True))
                except:
                    pass
        
        # 馬番
        umaban_cell = row.select_one('td[class*="Umaban"]')
        if umaban_cell:
            text = umaban_cell.get_text(strip=True)
            if text.isdigit():
                horse.number = int(text)
        
        # 馬名とID
        horse_name_link = row.select_one('span.HorseName a')
        if horse_name_link:
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
        
        # 斤量
        cells = row.select('td')
        for cell in cells:
            text = cell.get_text(strip=True)
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
        
        # オッズ
        odds_span = row.select_one('td.Popular span[id^="odds-"]')
        if odds_span:
            try:
                odds_text = odds_span.get_text(strip=True)
                if odds_text != '---.-':
                    horse.odds = float(odds_text)
            except:
                pass
        
        if horse.name and horse.number > 0:
            horses.append(horse)
    
    return race_info, horses


def parse_horse_history(html: str) -> List[RaceResult]:
    """馬の過去成績を解析"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    table = soup.select_one('table.db_h_race_results')
    if not table:
        table = soup.select_one('table.nk_tb_common')
    
    if not table:
        return results
    
    tbody = table.select_one('tbody')
    rows = tbody.select('tr') if tbody else table.select('tr')
    
    for row in rows:
        cells = row.select('td')
        if len(cells) < 15:
            continue
        
        result = RaceResult()
        
        try:
            date_link = cells[0].select_one('a')
            result.date = date_link.get_text(strip=True) if date_link else cells[0].get_text(strip=True)
            
            course_link = cells[1].select_one('a')
            result.course = course_link.get_text(strip=True) if course_link else cells[1].get_text(strip=True)
            
            race_link = cells[4].select_one('a')
            result.race_name = race_link.get_text(strip=True) if race_link else cells[4].get_text(strip=True)
            
            try:
                result.total_horses = int(cells[6].get_text(strip=True))
            except:
                pass
            
            finish_text = cells[11].get_text(strip=True)
            if finish_text.isdigit():
                result.finish = int(finish_text)
            else:
                continue
            
            dist_text = cells[14].get_text(strip=True)
            dist_match = re.search(r'([芝ダ障])(\d{3,4})', dist_text)
            if dist_match:
                result.track_type = 'ダート' if dist_match.group(1) == 'ダ' else '芝'
                result.distance = int(dist_match.group(2))
            
            try:
                result.odds = float(cells[9].get_text(strip=True))
            except:
                pass
            
            try:
                result.popularity = int(cells[10].get_text(strip=True))
            except:
                pass
            
            results.append(result)
            
        except:
            continue
    
    return results[:20]


def calculate_score(horse: Horse, race_info: RaceInfo, all_horses: List[Horse]) -> Dict:
    """馬のスコアを計算"""
    score_details = {}
    total_score = 0
    
    results = horse.results
    
    # 近走成績 (35%)
    recent_score = 50
    if results:
        weights = [0.35, 0.25, 0.2, 0.12, 0.08]
        weighted_sum = 0
        for i, r in enumerate(results[:5]):
            if i < len(weights):
                finish_score = max(0, 100 - (r.finish - 1) * 12)
                weighted_sum += finish_score * weights[i]
        recent_score = weighted_sum
    score_details['recent'] = recent_score
    total_score += recent_score * 0.40
    
    # 勝率・複勝率 (15%)
    basic_score = 50
    if results:
        wins = sum(1 for r in results if r.finish == 1)
        places = sum(1 for r in results if r.finish <= 3)
        win_rate = wins / len(results)
        place_rate = places / len(results)
        basic_score = win_rate * 50 + place_rate * 50
    score_details['basic'] = basic_score
    total_score += basic_score * 0.15
    
    # 距離適性 (12%)
    distance_score = 50
    if results and race_info.distance:
        same_dist = [r for r in results if abs(r.distance - race_info.distance) <= 100]
        if same_dist:
            places = sum(1 for r in same_dist if r.finish <= 3)
            distance_score = (places / len(same_dist)) * 100
    score_details['distance'] = distance_score
    total_score += distance_score * 0.11
    
    # コース適性 (8%)
    course_score = 50
    if results and race_info.course:
        same_course = [r for r in results if race_info.course in r.course]
        if same_course:
            places = sum(1 for r in same_course if r.finish <= 3)
            course_score = (places / len(same_course)) * 100
    score_details['course'] = course_score
    total_score += course_score * 0.08
    
    # 枠順 (8%)
    draw_score = 50
    total = len(all_horses)
    if horse.number and total > 0:
        position = (horse.number - 1) / max(total - 1, 1)
        inner_bias = 0.2 if race_info.distance <= 1400 else 0.1
        draw_score = (1 - position * inner_bias) * 100
    score_details['draw'] = draw_score
    total_score += draw_score * 0.05
    
    # オッズ評価 (10%)
    odds_score = 50
    if horse.odds and horse.odds > 0:
        odds_score = max(0, 100 - math.log(horse.odds) * 18)
    score_details['odds'] = odds_score
    total_score += odds_score * 0.10
    
    # 安定性 (7%)
    stability_score = 50
    if len(results) >= 3:
        finishes = [r.finish for r in results[:10]]
        import statistics
        std = statistics.stdev(finishes) if len(finishes) > 1 else 0
        stability_score = max(0, 100 - std * 12)
    score_details['stability'] = stability_score
    total_score += stability_score * 0.07
    
    # 斤量 (5%)
    weight_score = 50
    weights = [h.weight_carry for h in all_horses if h.weight_carry > 0]
    if weights and horse.weight_carry:
        avg_weight = sum(weights) / len(weights)
        diff = horse.weight_carry - avg_weight
        weight_score = 50 - diff * 8
        weight_score = max(0, min(100, weight_score))
    score_details['weight'] = weight_score
    total_score += weight_score * 0.04
    
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
    
    predictions.sort(key=lambda x: x['score'], reverse=True)
    
    scores = [p['score'] for p in predictions]
    min_s, max_s = min(scores), max(scores)
    
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
        
        if p['horse'].odds and p['horse'].odds > 0:
            p['expected_value'] = p['win_prob'] * p['horse'].odds
        else:
            p['expected_value'] = 0
    
    return predictions


def get_gemini_analysis(race_info: RaceInfo, horses: List[Horse], predictions: List[Dict], api_key: str) -> str:
    """Gemini AIによる分析"""
    try:
        genai.configure(api_key=api_key)
        # gemini-2.0-flash は無料枠で利用可能
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # レース情報を整形
        race_summary = f"""
レース: {race_info.race_name}
競馬場: {race_info.course}
距離: {race_info.distance}m ({race_info.track_type})
馬場状態: {race_info.track_condition or '不明'}
出走頭数: {len(horses)}頭
"""
        
        # 馬情報を整形
        horse_data = []
        for p in predictions[:10]:  # 上位10頭
            h = p['horse']
            recent = '-'.join(str(r.finish) for r in h.results[:5]) if h.results else '新馬'
            horse_data.append(f"  {p['rank']}位 {h.number}番 {h.name} ({h.sex}{h.age}) 騎手:{h.jockey} 近走:{recent} 勝率予測:{p['win_prob']*100:.1f}%")
        
        prompt = f"""あなたは競馬予想の専門家です。以下のレース情報と出走馬データを分析し、予想と解説を日本語で提供してください。

【レース情報】
{race_summary}

【出走馬データ（統計モデル予測順）】
{chr(10).join(horse_data)}

以下の観点から分析してください：
1. 本命馬の選定理由（◎）
2. 対抗馬の選定理由（○）
3. 穴馬候補とその理由（▲）
4. レース展開予想
5. 推奨買い目（単勝、馬連、3連複）
6. 注意点やリスク

簡潔かつ的確に分析してください（500文字程度）。
"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"AI分析エラー: {str(e)}"


def main():
    # ヘッダー
    st.markdown('<p class="main-header">🏇 競馬AI予測システム</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Gemini-2.5-Pro × 統計モデルによる高精度予測</p>', unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # API Key
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Google AI StudioでAPIキーを取得してください"
        )
        
        st.markdown("---")
        
        # レースID入力
        race_id = st.text_input(
            "レースID",
            value="202508040701",
            help="netkeibaのURLからレースIDを入力"
        )
        
        st.markdown("---")
        
        st.markdown("""
        ### 📖 使い方
        1. Gemini API Keyを入力
        2. レースIDを入力
        3. 「予測開始」ボタンをクリック
        
        ### 🔗 レースIDの取得方法
        netkeibaの出馬表URLから取得:
        ```
        race_id=XXXXXXXXXXXX
        ```
        の部分をコピー
        """)
    
    # メインコンテンツ
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        predict_button = st.button("🔮 予測開始", type="primary", use_container_width=True)
    
    if predict_button and race_id:
        # プログレスバー
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. 出馬表取得
        status_text.text("📥 出馬表を取得中...")
        progress_bar.progress(10)
        
        html = fetch_race_page(race_id)
        if not html:
            st.error("❌ 出馬表の取得に失敗しました。レースIDを確認してください。")
            return
        
        # 2. 解析
        status_text.text("📊 データを解析中...")
        progress_bar.progress(20)
        
        race_info, horses = parse_race_page(html, race_id)
        
        if not horses:
            st.error("❌ 馬データを取得できませんでした")
            return
        
        # 3. 各馬の成績取得
        status_text.text("📈 各馬の過去成績を取得中...")
        for i, horse in enumerate(horses):
            if horse.horse_id:
                horse_html = fetch_horse_page(horse.horse_id)
                if horse_html:
                    horse.results = parse_horse_history(horse_html)
            progress_bar.progress(20 + int(50 * (i + 1) / len(horses)))
            time.sleep(0.2)
        
        # 4. 予測実行
        status_text.text("🔮 予測モデルを実行中...")
        progress_bar.progress(75)
        predictions = predict(horses, race_info)
        
        # 5. AI分析
        ai_analysis = ""
        if api_key:
            status_text.text("🤖 Gemini AI分析中...")
            progress_bar.progress(85)
            ai_analysis = get_gemini_analysis(race_info, horses, predictions, api_key)
        
        progress_bar.progress(100)
        status_text.text("✅ 完了!")
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()
        
        # 結果表示
        st.markdown("---")
        
        # レース情報
        st.header(f"🏁 {race_info.race_name}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("競馬場", race_info.course or "不明")
        with col2:
            st.metric("距離", f"{race_info.distance}m")
        with col3:
            st.metric("コース", race_info.track_type or "不明")
        with col4:
            st.metric("出走頭数", f"{len(horses)}頭")
        
        st.markdown("---")
        
        # 予測結果
        st.header("🏆 予測ランキング")
        
        # トップ3
        col1, col2, col3 = st.columns(3)
        
        marks = ['◎ 本命', '○ 対抗', '▲ 単穴']
        colors = ['🥇', '🥈', '🥉']
        
        for i, (col, mark, color) in enumerate(zip([col1, col2, col3], marks, colors)):
            if i < len(predictions):
                p = predictions[i]
                h = p['horse']
                with col:
                    st.markdown(f"### {color} {mark}")
                    st.markdown(f"**{h.number}番 {h.name}**")
                    st.markdown(f"騎手: {h.jockey}")
                    recent = '-'.join(str(r.finish) for r in h.results[:3]) if h.results else '-'
                    st.markdown(f"近走: {recent}")
                    st.metric("勝率予測", f"{p['win_prob']*100:.1f}%")
        
        st.markdown("---")
        
        # 全馬データテーブル
        st.header("📋 全出走馬データ")
        
        table_data = []
        for p in predictions:
            h = p['horse']
            recent = '-'.join(str(r.finish) for r in h.results[:3]) if h.results else '-'
            table_data.append({
                '順位': p['rank'],
                '馬番': h.number,
                '馬名': h.name,
                '性齢': f"{h.sex}{h.age}",
                '騎手': h.jockey,
                '斤量': h.weight_carry,
                '近走': recent,
                '勝率': f"{p['win_prob']*100:.1f}%",
                'スコア': f"{p['norm_score']:.3f}",
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # 買い目推奨
        st.header("🎯 買い目推奨")
        
        top5 = predictions[:5]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 堅実派")
            st.markdown(f"**単勝**: {top5[0]['horse'].number}番")
            st.markdown(f"**馬連**: {top5[0]['horse'].number}-{top5[1]['horse'].number}")
            st.markdown(f"**ワイド**: {top5[0]['horse'].number}-{top5[1]['horse'].number}, {top5[0]['horse'].number}-{top5[2]['horse'].number}")
        
        with col2:
            st.markdown("### 攻め派")
            st.markdown(f"**3連複**: {top5[0]['horse'].number}-{top5[1]['horse'].number}-{top5[2]['horse'].number}")
            st.markdown(f"**3連単**: {top5[0]['horse'].number}→{top5[1]['horse'].number}→{top5[2]['horse'].number}")
            # 期待値上位
            ev_sorted = sorted([p for p in predictions if p['expected_value'] > 0], 
                              key=lambda x: x['expected_value'], reverse=True)
            if ev_sorted:
                st.markdown(f"**穴狙い**: {ev_sorted[0]['horse'].number}番 (期待値: {ev_sorted[0]['expected_value']:.2f})")
        
        st.markdown("---")
        
        # AI分析
        if ai_analysis:
            st.header("🤖 Gemini AI分析")
            st.markdown(ai_analysis)
        elif not api_key:
            st.info("💡 Gemini API Keyを入力すると、AIによる詳細分析が表示されます")
        
        st.markdown("---")
        
        # 免責事項
        st.warning("⚠️ 本予測は参考情報です。馬券購入は自己責任でお願いします。")


if __name__ == '__main__':
    main()
