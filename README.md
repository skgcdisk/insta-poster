# insta-poster

Instagram への画像投稿を自動化する Windows デスクトップアプリです。

画像をドラッグ＆ドロップするだけで、AI による安全チェック・キャプション生成・画像補正を行い、
指定日時に自動投稿します。

---

## 主な機能

- **複数画像のドラッグ＆ドロップ** — JPG / PNG / WEBP 対応・複数ファイル同時 OK
- **AI 安全チェック** — Gemini API が公序良俗に反する画像を自動検出して除外
- **AI キャプション自動生成** — 絵文字・ハッシュタグ付きの日本語キャプションを生成
- **画像自動補正** — 明るさ・コントラスト・彩度を自動調整
- **スケジュール投稿** — 開始日時を設定すると 1 日おきに自動投稿（個別日時の手動設定も可）
- **キャプション編集** — 生成されたキャプションをアプリ上から自由に編集可能
- **AI プロンプト編集** — キャプション生成のプロンプトを設定タブからカスタマイズ可能

---

## 必要なもの

| サービス | 用途 | 取得先 |
|---|---|---|
| Gemini API キー | 安全チェック・キャプション生成 | [Google AI Studio](https://aistudio.google.com/) |
| Instagram ビジネスアカウント | 投稿先 | [Instagram](https://www.instagram.com/) |
| Meta Graph API アクセストークン | Instagram API 認証 | [Meta Business Suite](https://business.facebook.com/) |
| imgbb API キー | 画像の一時公開 URL 生成 | [imgbb.com](https://api.imgbb.com/) |

---

## インストール方法

### 方法 A：インストーラーを使う（推奨）

1. [Releases](../../releases) から最新の `insta-poster-setup.exe` をダウンロード
2. ダブルクリックしてインストール
3. スタートメニュー or デスクトップのショートカットから起動

### 方法 B：ソースから実行する（開発者向け）

```bash
# 1. リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/insta-poster.git
cd insta-poster

# 2. 仮想環境を作成して有効化
python -m venv .venv
.venv\Scripts\activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 起動
python main.py
```

---

## 初期設定

アプリを起動したら「設定」タブで以下を入力して「💾 保存する」を押してください。

1. **Gemini API キー** — Google AI Studio で取得
2. **Instagram ユーザー ID** — Instagram ビジネスアカウントの数字 ID
3. **Instagram アクセストークン** — Meta Business Suite のシステムユーザートークン
4. **imgbb API キー** — imgbb.com で取得した無料 API キー

---

## 使い方

1. 「メイン」タブに画像をドラッグ＆ドロップ
2. **「✨ 一括処理」** を押す → AI が安全チェック・画像補正・キャプション生成を実行
3. 必要に応じて **✏️ ボタン** でキャプションを編集
4. 開始日時を入力して **「▶ スケジュール開始」** を押す → 1 日おきに自動投稿

---

## 動作環境

| OS | 状況 |
|---|---|
| Windows 10 / 11 | ✅ 動作確認済み |
| macOS | 🔺 理論上は動作するが未検証 |
| Linux | 🔺 理論上は動作するが未検証 |
| iOS / Android | ❌ 非対応 |

---

## 技術スタック

- **UI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)（ダークテーマ）
- **ドラッグ＆ドロップ**: [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2)
- **画像処理**: [Pillow](https://pillow.readthedocs.io/)
- **AI**: [Gemini API](https://ai.google.dev/) (`gemini-2.5-flash`)
- **Instagram 投稿**: [Meta Graph API](https://developers.facebook.com/docs/instagram-api/) + [imgbb](https://imgbb.com/)
- **スケジューラー**: [APScheduler](https://apscheduler.readthedocs.io/) + SQLite

---

## ライセンス

MIT License
