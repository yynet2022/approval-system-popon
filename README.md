# 承認システム - ポポン (Approval System Popon)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Django を用いたシンプルかつ拡張性の高い Web ベースの承認ワークフローシステムです。
「簡易申請」や「近距離出張申請」など、業務に必要な申請フローを直感的な UI で管理できます。

## 🚀 主な特徴

*   **パスワードレス認証**: メールで届く「マジックリンク」をクリックするだけの簡単・安全なログイン（ステートフル認証）。
*   **柔軟な申請モデル**: マルチテーブル継承を採用し、共通の承認プロセスを維持しつつ、多様な申請タイプ（簡易申請、出張申請など）に対応。
*   **動的な承認ルート**: 申請ごとに最大5段階の承認者を柔軟に設定可能。`django-autocomplete-light` によるスムーズなユーザー検索。
*   **モダンな UI**: Bootstrap 5 を採用し、Ajax による快適な一覧表示や検索機能を提供。
*   **詳細な履歴管理**: 申請から承認、差戻し、却下までの全アクションをログとして記録。

## 📋 必要要件

*   Python 3.9 以上
*   Django 4.2 / 5.2
*   その他依存パッケージは `requirements.txt` を参照

## 🛠️ インストールとセットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-repo/approval-system-popon.git
cd approval-system-popon
```

### 2. 仮想環境の作成と有効化

Windows (Git Bash):
```bash
python -m venv venv
source venv/Scripts/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境設定 (.secrets.toml)

プロジェクトのルートで以下のコマンドを実行し、秘密鍵を含む設定ファイルを生成します。

```bash
python contrib/generate_secretkey.py >> config/.secrets.toml
```

必要に応じて `config/.secrets.toml` を編集し、`DEBUG = true` やデータベース設定を行ってください。

### 5. データベースの初期化

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. サイト設定の更新

デフォルトのドメインなどを環境に合わせて更新します。

```bash
python manage.py update_site --name "ポポン" --domain "localhost:8000"
```

### 7. 管理ユーザーの作成

```bash
python manage.py createsuperuser
```

### (オプション) テストデータの投入

開発用にダミーユーザーや申請データを作成できます。

```bash
python manage.py setup_test_data
```

## ▶️ 実行方法

開発サーバーを起動します。

```bash
python manage.py runserver
```

ブラウザで `http://localhost:8000` にアクセスしてください。

## 📚 ドキュメント

詳細な仕様や設計については `docs/` ディレクトリを参照してください。

*   [仕様書 (SPECIFICATION.md)](docs/SPECIFICATION.md)
*   [テスト仕様書 (TEST_SPECIFICATION.md)](docs/TEST_SPECIFICATION.md)
*   [新規申請タイプの追加手順 (add_new_approval.md)](docs/add_new_approval.md)

## 🤝 開発者向け (Makefile)

`make` コマンドが利用可能な環境では、以下のショートカットが使用できます。

*   `make all`: マイグレーションの実行
*   `make check`: Flake8 によるリントチェック
*   `make test`: テストの実行
*   `make clean`: キャッシュファイルの削除

## 📄 ライセンス

本プロジェクトは [MIT License](LICENSE) の下で公開されています。
