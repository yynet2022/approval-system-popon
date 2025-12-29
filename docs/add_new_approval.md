# 新しい申請タイプの追加手順

本システム（Ver 4.0以降）では、マルチテーブル継承とリファクタリングされた基盤により、比較的少ない手順で新しい申請タイプ（例：有給休暇申請、備品購入申請など）を追加できます。

既存の `views.py` や `request_detail.html` の条件分岐を修正する必要はありません。

## 必要な作業一覧

新しい申請タイプを追加するには、以下の5つのステップを実施します。

1.  **モデル作成**: `approvals/models.py`
2.  **フォーム作成**: `approvals/forms.py`
3.  **詳細表示テンプレート作成**: `templates/approvals/partials/detail_{modelname}.html`
4.  **作成ビュー作成**: `approvals/views.py`
5.  **URL登録**: `approvals/urls.py`

---

## 具体的な手順（例: 有給休暇申請 `PaidLeaveRequest`）

### Step 1: モデルの作成

`approvals/models.py` に、`Request` を継承したモデルクラスを追加します。

```python
# approvals/models.py

class PaidLeaveRequest(Request):
    """
    有給休暇申請モデル
    """
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

### Step 2: フォームの作成

`approvals/forms.py` に、作成画面用のフォームクラスを追加します。
`is_restricted` フィールドは必ず含めるようにしてください。

```python
# approvals/forms.py
from .models import PaidLeaveRequest

class PaidLeaveRequestForm(forms.ModelForm):
    class Meta:
        model = PaidLeaveRequest
        # 必要なフィールドを定義。is_restricted は必須。
        fields = ("title", "leave_date", "reason", "is_restricted")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "leave_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_restricted": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
```

### Step 3: 詳細表示テンプレート部品の作成

詳細画面（承認画面や閲覧画面）で表示する、この申請タイプ固有の部分だけを記述した HTML ファイルを作成します。
ファイル名は **`detail_{モデル名（全て小文字）}.html`** である必要があります。

*   パス: `templates/approvals/partials/detail_paidleaverequest.html`

```html
<!-- templates/approvals/partials/detail_paidleaverequest.html -->

<div class="row mb-3">
    <div class="col-md-2 text-muted">休暇取得日</div>
    <div class="col-md-10">{{ req.leave_date }}</div>
</div>
<div class="row mb-3">
    <div class="col-md-2 text-muted">取得理由</div>
    <div class="col-md-10" style="white-space: pre-wrap;">{{ req.reason }}</div>
</div>
```

### Step 4: 作成ビューの追加

`approvals/views.py` に、新規作成画面用の View を追加します。
`BaseRequestCreateView` を継承することで、承認ルート設定やメール送信処理などの共通機能を自動的に利用できます。

```python
# approvals/views.py
from .models import PaidLeaveRequest
from .forms import PaidLeaveRequestForm

class PaidLeaveRequestCreateView(BaseRequestCreateView):
    """有給休暇申請作成ビュー"""
    model = PaidLeaveRequest
    form_class = PaidLeaveRequestForm
    request_prefix = "REQ-P"  # 申請番号のプレフィックス（任意）
```

**重要**: `views.py` の `forms` インポート部分で、新しいフォームクラスを読み込めるようにしておくか、`get_form_class` が動的に参照できるように `from . import forms` の記述があることを確認してください。

### Step 5: URLの登録

`approvals/urls.py` に、作成画面へのパスを追加します。

```python
# approvals/urls.py

urlpatterns = [
    # ... 既存のURL ...
    path(
        "create/paid-leave/",
        views.PaidLeaveRequestCreateView.as_view(),
        name="create_paid_leave"
    ),
]
```

### Step 6: マイグレーションの実行

最後にデータベースへ反映させます。

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 7: メニューへの追加（任意）

ユーザーがアクセスしやすいように、ポータル画面（`templates/portal/index.html` 等）の「新規申請」メニューにリンクを追加してください。

```html
<a class="dropdown-item" href="{% url 'approvals:create_paid_leave' %}">有給休暇申請</a>
```

---

## 仕組みの解説

*   **詳細表示の自動化**: `Request` モデルの `get_real_instance()` メソッドが自動的に子モデル（`PaidLeaveRequest`）を取得し、`detail_template_name` プロパティが対応するテンプレート部品（`partials/detail_paidleaverequest.html`）へのパスを返します。これにより、`RequestDetailView` は変更することなく新しい申請内容を表示できます。
*   **再申請の自動化**: `RequestUpdateView` も同様に、`get_real_instance()` と `form_class_name` プロパティを使って、自動的に適切なフォームクラス（`PaidLeaveRequestForm`）を選択します。
