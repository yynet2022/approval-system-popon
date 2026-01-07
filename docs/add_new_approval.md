# 新しい申請タイプの追加手順 (Ver 4.1)

本システム（仕様Ver 4.1以降）では、**モデルクラスを定義するだけ**で新しい申請タイプを追加できる「自動構成メカニズム」を導入しました。
煩雑なフォーム作成、ビュー定義、URL登録、メニュー編集は一切不要です。

## 手順概要

1.  **モデル作成**: `approvals/models/types.py`
2.  **DB反映**: マイグレーション実行
3.  **(任意) デザイン調整**: 詳細テンプレート作成

---

## 具体的な手順（例: 有給休暇申請 `PaidLeaveRequest`）

### Step 1: モデルの作成

`approvals/models/types.py` に、`Request` を継承したモデルクラスを追加します。
設定用のクラス属性 (`request_prefix`, `url_slug`) を記述することで、システムの挙動を制御できます。

```python
# approvals/models/types.py

class PaidLeaveRequest(Request):
    """
    有給休暇申請モデル
    """
    # 【必須】申請番号のプレフィックス
    request_prefix = "REQ-P"

    # 【任意】URL識別子（省略時はクラス名から自動生成: paidleaverequest -> paidleave）
    url_slug = "paid-leave"

    PTYPE_ALL = 0
    PTYPE_AM = 1
    PTYPE_PM = 2
    PTYPE_TIME = 3
    PTYPE_CHOICES = [
        (PTYPE_ALL, "終日"),
        (PTYPE_AM, "午前休"),
        (PTYPE_PM, "午後休"),
        (PTYPE_TIME, "時間休"),
    ]

    # 独自のフィールド定義
    leave_date = models.DateField(
        verbose_name="休暇取得日"
    )
    ptype = models.IntegerField(
        choices=PTYPE_CHOICES,
        default=PTYPE_ALL,
        verbose_name="タイプ"
    )
    reason = models.TextField(
        blank=True,
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

### フォームフィールドの高度なカスタマイズ（複数選択など）

デフォルトのフォーム生成ロジックでは対応できないフィールド（例: `JSONField` を使ったチェックボックス複数選択）を実装したい場合は、モデルクラスに `customize_formfield` クラスメソッドを定義します。

**例: 備品購入申請 `EquipmentRequest` (付属品を複数選択)**

```python
from django import forms
from django.db import models
from .base import Request

class EquipmentRequest(Request):
    request_prefix = "REQ-E"
    url_slug = "equipment"

    equipment_name = models.CharField(max_length=100, verbose_name="品名")

    # 選択肢の定義
    OPTION_CHOICES = [
        ("mouse", "マウス"),
        ("keyboard", "キーボード"),
        ("monitor", "モニター"),
        ("cable", "各種ケーブル"),
    ]

    # データはJSONFieldとして保存する（default=list で空リストを初期値に）
    options = models.JSONField(
        verbose_name="付属品オプション",
        default=list,
        blank=True
    )

    class Meta:
        verbose_name = "備品購入申請"
        verbose_name_plural = "備品購入申請"

    @classmethod
    def customize_formfield(cls, field, **kwargs):
        """
        フォームフィールドの生成をフックしてカスタマイズする
        """
        if field.name == "options":
            # 重要: システム側で自動設定される 'widget' 引数が衝突しないように除去する
            kwargs.pop("widget", None)
            
            # JSONField を MultipleChoiceField (CheckboxSelectMultiple) として扱う
            return forms.MultipleChoiceField(
                choices=cls.OPTION_CHOICES,
                widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
                **kwargs
            )
        
        # その他のフィールドは親クラスのデフォルト処理に任せる
        return super().customize_formfield(field, **kwargs)
```

**ポイント:**
1.  データストレージには `models.JSONField(default=list)` を使用します。
2.  `customize_formfield` で `field.name` をチェックし、対象フィールドの場合のみフォームフィールドのインスタンスを返します。
3.  **重要**: `kwargs.pop("widget", None)` を実行して、自動生成ロジックが渡してくるデフォルトのウィジェット設定を除去してください。これを行わないと「キーワード引数が重複している」というエラーが発生します。
