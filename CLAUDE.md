# kessan-reports — Claude Code プロジェクト指示

このリポジトリは決算短信PDFを業種別テーマのHTMLに変換して GitHub Pages で公開し、同時に Google スプレッドシート「決算情報」に行データを書き込むパイプライン。

---

## HTML 生成スタイル（必須・基準：8725_2026_Q4.html）

**カラースキーム（重要）：**
- 背景は **明るい色**（オフホワイト系 `#F7F6F2` など）。**全体を暗い背景にしない**
- カードは白 `#FFFFFF` + うっすら border
- 本文文字は **黒系**（`#1A1A1A` 等）。サブ情報は `#5A5A5A` 程度のグレー
- **プラスの数値は緑** `#1E7E4A`（クラス `.up`）
- **マイナスの数値は赤** `#C0392B`（クラス `.down`）
- 業種テーマカラーはヘッダー帯・アクセント・ウォーターマークなど**限定的**に使用（全面塗りつぶしには使わない）

**ヘッダー：**
- 業種テーマカラー（保険業＝Navy/Gold、製薬＝Red、小売＝Amber、卸売＝Steel など）を背景にしてOK
- ウォーターマーク文字は業種を反映（"Insurance" / "Auto" / "Industrial" / "Pharma" など）

**フォント：**
- 本文：`'Noto Sans JP', sans-serif`
- 見出し：`'Noto Serif JP', serif`
- 数値（KPI / 大型表示）：`'DM Serif Display', serif`
- Google Fonts を `<link>` で読み込む

**構成（必須セクション）：**
1. 事業概要
2. 業績ハイライト（KPI strip + セグメント別グリッド）
3. 財政状態
4. 配当
5. リスク/トピックス/特記事項
6. 総評（gold/accent ハイライトボックス）

**参照テンプレート：** `8725_2026_Q4.html`（保険業 Navy/Gold）の CSS/構造を踏襲。テーマカラーだけを業種に合わせて差し替える。

**既存HTMLの取り扱い：**
- すでに作成済みの `8766_2026_Q4.html` / `9882_2026_Q4.html` / `9986_2026_Q4.html` は暗い背景になっているが、**過去ファイルは修正しない**（ユーザー方針）
- 今後新規作成する HTML から本ガイドを適用

---

## ファイル名規約

`{証券コード4桁}_{決算期末西暦4桁}_{Q1|Q2|Q3|Q4}.html`

- 年度＝決算期末の西暦4桁（2026年3月期 → 2026）
- Q＝通期決算は Q4、第1〜3四半期は Q1/Q2/Q3
- 株式分割は分割後換算ベースで統一、分割前実績はカッコ書き注記

---

## パイプライン実行手順（「実行」と言われたとき）

1. `/tmp/gcreds.json` の存在確認（無ければ Drive MCP で file ID `1FhruS13G9wdAyF2Prs_SVjJEQsEugSIC` を取得して保存）
2. Drive フォルダ `1N8yVJ1wCQMqMg1hBxUC2A9hdv5RuHlCZ` の PDF を一覧
3. PDF名先頭4桁 = 証券コード。`ls {code}_*.html` で既存判定 → 存在なら SKIP（API課金ゼロ）
4. 新規PDFのみ `read_file_content` でテキスト抽出
5. 業種別テーマで HTML 生成（**本ガイドのスタイル厳守**）
6. feature branch に commit → main に cherry-pick → main を push（GitHub Pages 配信）
7. `tools/sheets.py` の `write_data(data, html_filename)` で Google Sheets に書込

---

## Google Sheets 仕様

- Spreadsheet ID: `12jLfVOv8IvVtEU254OBIeO-SgajGkOoRo-YJo_JU7MU`
- Sheet: `決算情報`
- C列は ArrayFormula 保護（書込禁止）
- Q列は `=HYPERLINK("https://kyon4166.github.io/kessan-reports/{file}","{year} {Q}")` 形式
- summary列など先頭が `+`/`-`/`=`/`@` の文字列は `_safe_text()` で escape 済（`tools/sheets.py`）

---

## ブランチ運用

- HTML本体 → `main`（GitHub Pages 配信元）
- ツール開発・実験 → `claude/pdf-html-automation-JWjzw`

---

## 詳細な作業履歴

`20260521_作業内容_決算短信整理.md` を参照。
