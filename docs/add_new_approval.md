# 新しい申請タイプの追加手順 (Ver 4.1)

本システム（Ver 4.1以降）では、**モデルクラスを定義するだけ**で新しい申請タイプを追加できる「自動構成メカニズム」を導入しました。
煩雑なフォーム作成、ビュー定義、URL登録、メニュー編集は一切不要です。

## 手順概要

1.  **モデル作成**: `approvals/models.py`
2.  **DB反映**: マイグレーション実行
3.  **(任意) デザイン調整**: 詳細テンプレート作成

---

## 具体的な手順（例: 有給休暇申請 `PaidLeaveRequest`）

### Step 1: モデルの作成

`approvals/models.py` に、`Request` を継承したモデルクラスを追加します。
設定用のクラス属性 (`request_prefix`, `url_slug`) を記述することで、システムの挙動を制御できます。

```python
# approvals/models.py

class PaidLeaveRequest(Request):
    """
    有給休暇申請モデル
    """
    # 【必須】申請番号のプレフィックス
    request_prefix = "REQ-P"
    
    # 【任意】URL識別子（省略時はクラス名から自動生成: paidleaverequest -> paidleave）
    url_slug = "paid-leave"

    # 独自のフィールド定義
    leave_date = models.DateField(
        verbose_name="休暇取得日"
    )
    reason = models.TextField(
        verbose_name="取得理由"
    )

    class Meta:
        verbose_name = "有給休暇申請"
        verbose_name_plural = "有給休暇申請"
```

### Step 2: マイグレーションの実行

データベースへ反映させます。

```bash
python manage.py makemigrations
python manage.py migrate
```

**以上で作業は完了です。**
サーバーを再起動すると、以下の機能が自動的に有効になります。

1.  **メニュー追加**: ポータルの「新規申請」ドロップダウンに「有給休暇申請」が表示されます。
2.  **入力画面**: `/approvals/create/paid-leave/` で申請フォーム（カレンダー入力付き）が表示されます。
3.  **詳細画面**: デフォルトのレイアウトで申請内容が表示されます。

---

## カスタマイズ（任意）

### 詳細画面のデザインを凝りたい場合

デフォルトの箇条書き表示ではなく、独自のレイアウト（2カラム表示や装飾など）を行いたい場合は、テンプレートファイルを作成するだけで自動的に切り替わります。

*   **ファイル名**: `detail_{モデル名（全て小文字）}.html`
*   **配置場所**: `templates/approvals/partials/`

**例**: `templates/approvals/partials/detail_paidleaverequest.html`

```html
<div class="alert alert-info">
    <strong>休暇日:</strong> {{ req.leave_date }}
</div>
<p>{{ req.reason|linebreaksbr }}</p>
```

このファイルを作成すると、詳細画面で優先的に使用されます。削除すればデフォルト表示に戻ります。
