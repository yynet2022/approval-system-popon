# **承認システム プログラム仕様書 ver4.0**

## **1\. 概要**

Django を用いた Web ベースの承認ワークフローシステム。
初期リリースでは「簡易承認」モデルのみであったが、ver4.0 より**マルチテーブル継承**を用いた拡張性の高い設計へと刷新し、「近距離出張申請」を追加実装した。
これにより、共通の承認プロセスを維持しつつ、多様な業務申請に柔軟に対応可能な基盤を確立している。
ユーザー認証にはパスワードレスの「マジックリンク」方式を採用する。
本ドキュメントは、システムの実装に必要な全ての仕様を定義するものである。

## **2\. 技術スタック**

* **言語**: Python 3.9 以上
* **フレームワーク**: Django 4.2 以上
* **データベース**:
  * 開発環境: SQLite
  * 本番環境: MySQL 8.0 以上 または PostgreSQL 13 以上
* **フロントエンド**:
  * HTML5 / CSS3
  * Bootstrap 5.3 (デザインフレームワーク)
  * JavaScript (ES6+)
  * **ライブラリ**: django-autocomplete-light (dal, dal_select2)
* **認証方式**: マジックリンク認証 (パスワードレス \+ ステートフル)
* **メール送信**: 同期処理 (SMTPサーバーとの通信完了を待機する。send\_mail関数を使用)
* **非同期処理**: 本バージョンでは実装しない。ただし、フロントエンドの一覧表示等にはAjaxを使用する。

## **3\. アプリケーション構成**

Djangoプロジェクトは「責務分離の原則」に基づき、以下のアプリケーションで構成する。

| アプリ名 | 役割 | 担当機能・ファイル |
| :---- | :---- | :---- |
| **config** | プロジェクト全体設定 | settings.py (設定, SITE\_ID, PROJECT\_NAME="ポポン"), urls.py, wsgi.py |
| **core** | 共通基盤 | 抽象モデル (BaseModel), 共通Mixins, context\_processors.py (common) |
| **accounts** | ユーザー管理 | カスタムUserモデル, LoginTokenモデル, 認証ビュー, オートコンプリートAPI |
| **portal** | ポータル画面 | トップページ（ダッシュボード）ビュー, **申請一覧・検索ロジック (Ajax対応)** |
| **notification** | お知らせ管理 | Notificationモデル, お知らせ一覧・詳細ビュー |
| **approvals** | 承認機能 | 申請モデル群(Request, SimpleRequest等), 申請CRUDビュー, 承認アクションビュー, services.py (NotificationService) |

## **4\. データモデル設計**

### **4.0. 共通基盤 (core)**

**抽象モデル: BaseModel** (Abstract Model)

* **概要**: 全ての具象モデルの親クラスとして機能し、共通フィールドを提供する。
* **継承**: django.db.models.Model
* **オプション (Meta)**: abstract \= True
* **フィールド定義**:
  1. **id**: UUIDField
     * primary\_key=True
     * default=uuid.uuid4
     * editable=False
  2. **created\_at**: DateTimeField
     * auto\_now\_add=True (作成時に現在日時を自動設定)
     * verbose\_name="作成日時"
  3. **updated\_at**: DateTimeField
     * auto\_now=True (保存時に現在日時を自動更新)
     * verbose\_name="更新日時"

### **4.1. ユーザー管理 (accounts)**

**モデル名: User** (Custom User Model)

* **概要**: システムを利用するユーザーのアカウント情報を管理する。
* **継承**: AbstractBaseUser, PermissionsMixin, core.models.BaseModel
* **フィールド定義**:
  1. **email**: EmailField
     * unique=True
     * blank=False, null=False
     * verbose\_name="メールアドレス"
  2. **last\_name**: CharField
     * max\_length=150
     * blank=True
     * verbose\_name="姓"
  3. **first\_name**: CharField
     * max\_length=150
     * blank=True
     * verbose\_name="名"
  4. **is\_staff**: BooleanField
     * default=False
     * verbose\_name="管理サイトアクセス権限"
  5. **is\_active**: BooleanField
     * default=False (メール認証完了後に True になる)
     * verbose\_name="有効フラグ"
  6. **is\_approver**: BooleanField
     * default=False
     * verbose\_name="承認者候補フラグ" (申請画面の選択肢に表示するか否か)
  7. **date\_joined**: DateTimeField
     * default=django.utils.timezone.now
     * verbose\_name="登録日時"
* **マネージャー**: BaseUserManager を継承したカスタムマネージャーを使用し、create\_user, create\_superuser メソッドを実装する。
* **メソッド詳細**:
  * **get\_full\_name()**:
    * ロジック: f"{self.last\_name} {self.first\_name}".strip()
    * 説明: 姓と名を半角スペースで結合して返す。両方未入力の場合は空文字を返す。
  * **get\_display\_name()**:
    * ロジック: return self.get\_full\_name() or self.email
    * 説明: フルネームがあればそれを返し、なければメールアドレスを返す。
  * **str()**:
    * ロジック: return self.get\_display\_name()
* **設定**: USERNAME\_FIELD \= 'email', REQUIRED\_FIELDS \= \[\]

**モデル名: LoginToken** (ステートフル認証用)

* **概要**: マジックリンク認証に使用する一時的なトークンを管理する。
* **継承**: core.models.BaseModel
* **フィールド定義**:
  1. **user**: ForeignKey
     * to: settings.AUTH\_USER\_MODEL
     * on\_delete=models.CASCADE
     * related\_name="login\_tokens"
  2. **token**: CharField
     * max\_length=64
     * unique=True
     * db\_index=True (検索高速化)
  3. **expires\_at**: DateTimeField
* **メソッド**:
  * **create\_token(user)** (クラスメソッドまたはマネージャーメソッド):
    * トークン生成: secrets.token\_urlsafe(32) を使用。
    * 有効期限設定: timezone.now() \+ timedelta(minutes=30)。
    * インスタンスを作成して保存し、返す。

### **4.2. お知らせ (notification)**

**モデル名: Notification**

* **概要**: システムからユーザーへのお知らせを管理する。
* **継承**: core.models.BaseModel
* **フィールド定義**:
  1. **title**: CharField
     * max\_length=255
     * verbose\_name="タイトル"
  2. **content**: TextField
     * verbose\_name="本文"
  3. **published\_at**: DateTimeField
     * default=django.utils.timezone.now
     * verbose\_name="公開日時" (表示順序の基準となる日時)
     * *注釈: 画面に表示される日付。created\_at と異なり、ユーザーが任意の日付（過去日など）に変更可能。*

### **4.3. 承認機能 (approvals)**

**【申請モデル構造 (マルチテーブル継承)】**

全ての申請は `Request` モデルを継承し、共通の承認ステータス管理機能を持つ。

**基底モデル: Request** (Multi-table Inheritance Parent)

* **概要**: 全ての申請タイプに共通する基本情報と現在のステータスを管理する。
* **継承**: core.models.BaseModel
* **フィールド定義**:
  1. **request\_number**: CharField
     * max\_length=20
     * unique=True
     * verbose\_name="申請番号"
     * フォーマット例: "REQ-S-202512-0001" (種別プレフィックス + ハイフン + 年月 + ハイフン + 連番)
  2. **applicant**: ForeignKey
     * to: settings.AUTH\_USER\_MODEL
     * on\_delete=models.PROTECT (ユーザー削除時に申請が消えないよう保護)
     * verbose\_name="申請者"
  3. **title**: CharField
     * max\_length=100
     * verbose\_name="件名"
  4. **status**: IntegerField
     * choices:
       * 0: Draft (下書き)
       * 1: Pending (申請中)
       * 2: Approved (承認完了)
       * 3: Remanded (差戻)
       * 4: Withdrawn (取り下げ)
       * 9: Rejected (却下)
     * default=0
     * verbose\_name="ステータス"
  5. **current\_step**: IntegerField
     * default=1
     * verbose\_name="現在のステップ"
  6. **submitted\_at**: DateTimeField
     * null=True, blank=True
     * verbose\_name="申請日時"
  7. **is\_restricted**: BooleanField
     * default=False
     * verbose\_name="閲覧制限フラグ"
     * 説明: Trueの場合、**申請者本人および承認ルートに含まれるユーザー（承認者・過去の承認者含む）のみ**閲覧可能。これ以外のユーザー（管理者含む）の通常画面（一覧・詳細）には表示されない。

**具象モデルA: SimpleRequest** (簡易承認申請)

* **概要**: 件名と自由記述の内容のみを持つシンプルな申請。
* **継承**: Request
* **フィールド定義**:
  1. **content**: TextField
     * verbose\_name="内容"

**具象モデルB: LocalBusinessTripRequest** (近距離出張申請)

* **概要**: 日帰りなどの近距離出張用の申請。
* **継承**: Request
* **フィールド定義**:
  1. **trip\_date**: DateField
     * verbose\_name="日程"
  2. **destination**: CharField
     * max\_length=100
     * verbose\_name="行先"
  3. **note**: TextField
     * blank=True
     * verbose\_name="補足事項"

---

**モデル名: Approver** (承認者設定)

* **概要**: 各申請における承認ルート（誰が、どの順番で承認するか）を管理する。
* **継承**: core.models.BaseModel
* **フィールド定義**:
  1. **request**: ForeignKey
     * to: **Request**
     * on\_delete=models.CASCADE
     * related\_name="approvers"
  2. **user**: ForeignKey
     * to: settings.AUTH\_USER\_MODEL
     * on\_delete=models.PROTECT
     * verbose\_name="承認者"
  3. **order**: IntegerField
     * verbose\_name="順序"
     * 制約: 1 から 5 の整数。
  4. **status**: IntegerField
     * choices:
       * 0: Pending (未処理)
       * 1: Approved (承認)
       * 2: Remanded (差戻)
       * 9: Rejected (却下)
     * default=0
     * verbose\_name="判定状態"
  5. **comment**: TextField
     * blank=True
     * verbose\_name="承認者コメント"
  6. **processed\_at**: DateTimeField
     * null=True, blank=True
     * verbose\_name="処理日時"
* **Metaオプション**:
  * ordering \= \['order'\] (順序順で取得)

**モデル名: ApprovalLog** (承認履歴ログ)

* **概要**: 申請に対する全てのアクション履歴を記録する。再申請でルートがリセットされてもこの記録は永続化される。
* **継承**: core.models.BaseModel
* **フィールド定義**:
  1. **request**: ForeignKey
     * to: **Request**
     * on\_delete=models.CASCADE
     * related\_name="logs"
  2. **actor**: ForeignKey
     * to: settings.AUTH\_USER\_MODEL
     * on\_delete=models.PROTECT
     * verbose\_name="実行者"
  3. **action**: IntegerField
     * choices:
       * 1: Submit (申請)
       * 2: Approve (承認)
       * 3: Remand (差戻)
       * 4: Resubmit (再申請)
       * 5: Withdraw (取り下げ)
       * 9: Reject (却下)
       * 10: ProxyRemand (代理差戻)
     * verbose\_name="アクション"
  4. **step**: IntegerField
     * null=True, blank=True
     * verbose\_name="実行時のステップ"
  5. **comment**: TextField
     * blank=True, null=True
     * verbose\_name="コメント"
* **Metaオプション**:
  * ordering \= \['created\_at'\] (時系列順)

## **5\. 機能要件詳細とロジック**

### **5.1. 認証機能 (Magic Link)**

1. **ログインページ (/accounts/login/)**
   * **入力項目**: メールアドレス (email)
     * ※URLパラメータ ?next=/path/to/redirect/ がある場合、これをフォームの hidden フィールド等で保持する。
   * **処理**:
     1. 入力されたメールアドレスでユーザーを**自動作成**または取得する (User.objects.get\_or\_create)。
        * 新規作成時のデフォルト値: is\_active=False, is\_staff=False, is\_approver=False。
     2. **トークン発行**:
        * LoginToken.objects.create(user=user, ...) でトークンを生成。
        * トークンを含むログイン用URLを作成（例: https://domain.com/accounts/login/verify/\<token\>/）。
        * **Redirect処理**: next パラメータが存在する場合、生成するURLのクエリパラメータとして付与する（例: .../verify/\<token\>/?next=/approvals/123/）。
     3. **メール送信**:
        * send\_mail を使用してメール送信。件名:「\[ポポン\] ログインURLのお知らせ」、本文: URLのみのシンプルなもの。
        * ※存在チェックは行わず、全ての入力に対してメールを送信する（自動登録仕様）。
2. **トークン検証ページ (/accounts/login/verify/\<token\>/)**
   * **処理**:
     1. URLのトークン文字列で LoginToken を検索。
     2. **無効判定**: レコードがない、expires\_at が現在時刻より過去。
        * 結果: エラー画面「無効なリンクか、有効期限切れです」を表示。
     3. **有効判定**:
        * **トークン削除**: token\_record.delete() を実行し、使用済みトークンを物理削除する。
        * user.is\_active \= True に更新（初回ログイン時の有効化）。
        * **注意**: is\_staff 等の権限フラグの自動更新は行わない（管理者が別途設定する）。
        * django.contrib.auth.login(request, user) を実行してセッション確立。
        * **リダイレクト**:
          * URLパラメータ next が存在し、かつ安全な内部URL（url\_has\_allowed\_host\_and\_scheme等でチェック）であれば、そのURLへリダイレクトする。
          * それ以外の場合は、ポータルトップ (/) へリダイレクトする。
3. **API用認証 (ApiLoginRequiredMixin)**
   * 未ログイン状態でAPIアクセスがあった場合、ログイン画面へのリダイレクトではなく `403 Forbidden` を返す。

### **5.2. 申請・承認ワークフロー**

※ 通知ロジックは `approvals.services.NotificationService` に集約する。

#### **A. 新規申請 (Create / Submit)**

* **画面**: 申請作成画面
  * 簡易申請: `/approvals/create/simple/`
  * 近距離出張申請: `/approvals/create/trip/`
* **申請種別の選択**: ポータルの「新規申請」ドロップダウンから選択する。
* **入力項目 (共通)**:
  * 件名 (title)
  * 閲覧制限設定 (is\_restricted): チェックボックス。
* **入力項目 (種別固有)**:
  * **簡易申請**: 内容 (content)
  * **近距離出張申請**: 日程 (trip\_date), 行先 (destination), 補足事項 (note)
* **承認者設定UI (動的フォーム)**:
  * 初期表示で入力欄を **2枠** 表示する。
  * 「＋」ボタン等で最大 **5枠** まで追加可能にする。
  * **入力方式**: `django-autocomplete-light` (ApproverAutocomplete) を使用。
    * **検索語句なし**: `is_approver=True` のユーザーのみ表示（よく使う承認者）。
    * **検索語句あり**: `is_active=True` の全ユーザーから検索。ただし結果は `is_approver=True` のユーザーを優先表示する。
    * **除外**: 自分自身（申請者）は選択肢に出さない。
* **バリデーション**:
  * 承認者が1名以上選択されていること。
  * 承認者に申請者本人が含まれていないこと。
  * 同じ承認者が連続していないこと (A \-\> A は不可。A \-\> B \-\> A は可)。
* **保存処理 (下書き保存 / 申請)**:
  1. **トランザクション開始 (transaction.atomic)**。
  2. **採番ロック**:
     * Request.objects.select\_for\_update() を用いて、種別ごとの現在の月（YYYYMM）の最大連番を取得。
     * なければ 0001、あれば \+1 して request\_number を生成。
     * プレフィックス: 簡易申請 `REQ-S-`, 近距離出張 `REQ-L-`
  3. 各申請モデル (SimpleRequest / LocalBusinessTripRequest) を保存。
  4. **Approver** レコードを入力順(order)に合わせて一括作成。
  5. **ログ記録**: ApprovalLog (Action: Submit) を作成。
  6. **メール通知**: 最初の承認者 (order=1) へ「承認依頼」メールを送信。
  7. トランザクションコミット。

#### **B. 承認アクション (Approve)**

* **対象**: `Request` モデルに対して操作を行うため、申請種別を問わず共通の処理となる。
* **権限**: ログインユーザーが、現在のステップ (current\_step) の Approver に設定されており、かつその status が Pending であること。
* **入力項目**: コメント (任意)
* **処理**:
  1. **トランザクション開始**。
  2. Request を select\_for\_update() でロック取得。
  3. **状態チェック**: Request.status が Pending 以外（取り下げ済み等）ならエラーメッセージを表示して中断。
  4. 現在の承認者の Approver を更新: status=Approved, comment=..., processed\_at=now.
  5. **次ステップ判定**:
     * 次の順序 (order \+ 1\) の承認者が存在する場合:
       * Request.current\_step を \+1。
       * 次の承認者へ「承認依頼」メール送信。
     * 次の承認者がいない場合 (最終承認):
       * Request.status を Approved に更新。
       * 申請者および承認ルート全ユーザーへ「承認完了」メール送信。
  6. **ログ記録**: ApprovalLog (Action: Approve) 作成。
  7. トランザクションコミット。
* **メール送信エラー時の挙動**: try-except で send\_mail を囲む。エラー時はログ出力し、画面には「承認は完了しましたが、通知メール送信に失敗しました」と表示する。処理自体はロールバックしない。

#### **C. 差戻アクション (Remand)**

* **権限**: 承認アクションと同じ。
* **入力項目**: コメント (**必須**)
* **処理**:
  1. **トランザクション開始**、ロック取得、状態チェック（承認と同様）。
  2. 現在の承認者の Approver を更新: status=Remanded, processed\_at=now.
  3. Request.status を Remanded に更新。
  4. **メール通知**:
     * **送信先**: 申請者、**本承認者（操作者）**、および **承認済の過去の承認者**。
     * **除外**: 未到来のステップの承認者には送信しない。
  5. **ログ記録**: ApprovalLog (Action: Remand) 作成。
  6. トランザクションコミット。

#### **D. 取り下げ (Withdraw)**

* **権限**: 申請者本人。
* **条件**: ステータスが `Pending`、`Approved`、または **`Remanded` (差戻)** の場合。
* **処理**:
  1. **トランザクション開始**。
  2. Request を select\_for\_update() でロック取得し、ステータスを Withdrawn に更新。
  3. **メール通知**:
     * 通常: **現在の承認者（Pending状態の承認者）** および **承認済の承認者** へ通知メール送信。
     * **例外 (Remandedからの取り下げ)**: 承認者への通知は行わない（既にプロセスが止まっているため）。
  4. **ログ記録**: ApprovalLog (Action: Withdraw) 作成。
  5. トランザクションコミット。

#### **E. 再申請 (Resubmit)**

* **権限**: 申請者本人。ステータスが Remanded の場合のみ。
* **入力項目**: 申請内容の修正、**承認ルートの再設定**が可能。
* **処理**:
  1. **トランザクション開始**。
  2. Request を select\_for\_update() でロック取得。
  3. **ルート更新 (洗い替え)**:
     * 既存の Approver レコードを**全て削除**する。
     * フォームで指定された承認者で Approver レコードを新規作成する。
  4. Request の current\_step を 1 に、status を Pending に戻す。
  5. **ログ記録**: ApprovalLog (Action: Resubmit) 作成。
  6. **メール通知**: 新しいルートの最初の承認者へメール送信。
  7. トランザクションコミット。

#### **F. 却下 (Reject)**

* **権限**: 現在の承認者（Pending時）または 承認ルートに含まれるユーザー（Approved時）。
* **条件**: ステータスが Pending または **Approved** の場合に実行可能（事後却下を含む）。
* **処理**:
  1. 入力チェック: コメント必須。
  2. **トランザクション開始**。
  3. Request を select\_for\_update() でロック取得し、ステータスを Rejected に更新。
  4. **メール通知**: 申請者、**現在の承認者**、および **承認済の承認者** へ「却下通知」を送信。
  5. **ログ記録**: ApprovalLog (Action: Reject) 作成。
  6. トランザクションコミット。

#### **G. 代理差戻し (Proxy Remand)**

* **権限**: is\_staff=True のユーザー。
* **条件**: ステータスが Pending または Approved。
* **入力項目**: コメント (**必須**)
* **処理**:
  1. **トランザクション開始**。
  2. Request を select\_for\_update() でロック取得し、ステータスを Remanded に強制変更。
  3. **ログ記録**: ApprovalLog (Action: ProxyRemand, Actor: 管理者) 作成。
  4. **メール通知**: 申請者、**現在の承認者（Pending状態）**、および **承認済の承認者** へメール送信（未到来の承認者には送信しない）。
  5. トランザクションコミット。

### **5.3. データ操作 (CRUD) 仕様マトリクス**

| 対象モデル | 操作 | 機能名称 | アクター | 画面/API (URL) | 主な処理内容・制約 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Request** (派生含む) | **Create** | **新規申請** | ログインユーザー | /approvals/create/**[type]**/ | ・typeにより Simple/Trip を切替 ・transaction.atomic下で保存 ・申請番号の排他採番 ・Approverの一括作成 ・初回メール通知 |
|  | **Read** | **全申請一覧 (検索)** | 全員 | / (GET) | ・親モデル `Request` を対象 ・is\_restrictedによるアクセス制御 ・キーワード検索、フィルタリング ・Ajaxページネーション |
|  | **Read** | **申請詳細** | 全員 | /approvals/\<uuid:pk\>/ (GET) | ・閲覧権限チェック(is\_restricted) ・関連するApprover一覧表示 ・ApprovalLog（履歴）表示 ・テンプレートで型判定し表示項目を切替 |
|  | **Update** | **再申請** | 申請者 | /approvals/\<uuid:pk\>/update/ (GET/POST) | ・status=Remandedの時のみ可 ・承認ルート全洗い替え ・フォームクラスを動的に切替 |
|  | **Update** | **ステータス更新** | (システム/各種) | (各Actionによる) | ・承認、差戻、却下、取り下げ、代理差戻しによる更新 ・排他制御 (select\_for\_update) 必須 |
|  | **Delete** | **物理削除** | 管理者 | /admin/ | ・**通常画面での削除機能は提供しない** ・Django管理サイトからのみ実行可能（監査ログ保持のため推奨しない） |
| **Approver** | **Create** | **承認者設定** | (システム) | (申請作成/再申請時) | ・申請保存時にバックエンドで自動生成 |
|  | **Read** | **承認者表示** | 全員 | /approvals/\<uuid:pk\>/ | ・申請詳細画面の一部として表示 |
|  | **Update** | **承認/差戻アクション** | 担当承認者 | /approvals/\<uuid:pk\>/action/ (POST) | ・ステータス、コメント、処理日時の更新 ・排他制御必須 |
|  | **Delete** | **ルート再構築** | (システム) | (再申請時) | ・再申請時に全削除して作り直す |
| **ApprovalLog** | **Create** | **ログ記録** | (システム) | (各アクション時) | ・申請、承認、差戻等のアクション実行時に自動生成 ・**Update/Deleteは不可**（証跡のため） |
| **Notification** | **CRUD** | **お知らせ管理** | 管理者 | /admin/ | ・Django管理サイトでのみ操作可能 |
| **User** | **Create** | **自動登録** | (システム) | /accounts/login/ (POST) | ・未登録メールアドレスでのログイン試行時に自動作成 |
|  | **Update** | **権限管理** | 管理者 | /admin/ | ・is\_staff, is\_approver等のフラグ変更は管理サイトで行う |

### **5.4. ポータル画面 (Top) の詳細仕様**

**共通仕様**: ログイン不要でアクセス可能。全ての申請一覧機能はこの画面に集約する。

1. **ヘッダーエリア**:
   * **未ログイン時**: 「ログイン」リンクを表示。
   * **ログイン時**: ユーザー名表示、「ログアウト」リンクを表示。
2. **お知らせエリア (Notifications)**:
   * Notification モデルのデータを published\_at の降順で表示。
   * Ajaxページネーションに対応（5件/ページ）。
   * 全ユーザー（未ログイン含む）が閲覧可能。
3. **【ログイン時のみ】承認依頼エリア (Pending Approvals)**:
   * **表示条件**: ログインユーザーに紐づく Approver レコードが存在し、かつその status が Pending の案件。
   * **場所**: お知らせエリアの下。
   * **内容**: 自分が今すぐ処理すべき申請のリスト。
4. **【ログイン時のみ】差戻し案件エリア (Remanded Requests)**:
   * **表示条件**: ログインユーザーが申請者であり、status が Remanded の案件。
   * **場所**: 承認依頼エリアの下。
   * **内容**: 再申請待ちの案件リスト。
5. **全申請一覧エリア (All Requests) \- メインコンテンツ**:
   * **概要**: 検索・フィルタ機能を備えたメインの一覧エリア。
   * **閲覧対象**:
     * **未ログインユーザー**: is\_restricted=False の申請のみ。
     * **ログインユーザー**: is\_restricted=False の申請 ＋ 自分が関係する is\_restricted=True の申請。
   * **機能**:
     * **キーワード検索**: タイトル、申請番号。
     * **フィルタ**: ステータス、申請者。
     * **ログイン時追加フィルタ**: 「自分の申請のみ表示」トグル（デフォルトON推奨）。
   * **ページネーション**: 1ページあたり20件。Ajaxによる部分更新に対応。

## **6\. 画面・URL構成一覧**

| No | 画面名称 | URLパターン | ビュー/機能概要 | 権限 |
| :---- | :---- | :---- | :---- | :---- |
| 1 | **ポータル (Top)** | / | ダッシュボード兼申請一覧。検索・フィルタ・Ajaxページネーション機能付き。 | 全員 |
| 2 | **ログイン** | /accounts/login/ | メールアドレス入力フォーム。送信後に送信完了メッセージを表示。 | 未ログイン |
| 3 | **ログイン検証** | /accounts/login/verify/\<str:token\>/ | トークン検証を行い、ログイン処理を実行してリダイレクトする(画面なし)。 | 全員 |
| 4 | **ログアウト** | /accounts/logout/ | ログアウト処理を実行し、Topへリダイレクト。 | ログイン済 |
| 5 | **お知らせ詳細** | /notifications/\<uuid:pk\>/ | お知らせの本文全文表示。 | 全員 |
| 6-1 | **簡易申請作成** | /approvals/create/simple/ | 新規申請フォーム (SimpleRequestForm)。 | ログイン済 |
| 6-2 | **出張申請作成** | /approvals/create/trip/ | 新規申請フォーム (LocalBusinessTripRequestForm)。 | ログイン済 |
| 7 | **申請詳細** | /approvals/\<uuid:pk\>/ | 申請内容（種別により表示切替）、現在の承認状況、履歴ログの表示。 | 全員 (制限あり) |
| 8 | **承認アクション** | /approvals/\<uuid:pk\>/action/ | 承認/差戻/却下処理を受け付けるPOST専用エンドポイント。 | 該当する承認者 |
| 9 | **管理サイト** | /admin/ | Django標準管理画面。User, Notification, 承認データのCRUD。 | is\_staff=True |

## **7\. ディレクトリ構成詳細**

```
project_root/
├── manage.py                    # Django管理コマンド
├── config/                      # プロジェクト設定ディレクトリ
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py             # 設定ファイル (SITE_ID, PROJECT_NAME)
│   ├── urls.py                 # ルートURL (includeを使用)
│   └── wsgi.py
├── core/                        # 共通基盤アプリ
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── context_processors.py   # 共通コンテキスト (common)
│   ├── mixins.py               # 共通Mixin (View用)
│   ├── models.py               # BaseModel 定義
│   └── tests.py
├── accounts/                    # ユーザー管理アプリ
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py               # User, LoginToken
│   ├── urls.py                 # /accounts/ 配下のURL
│   └── views.py                # LoginView, VerifyTokenView, ApproverAutocomplete
├── portal/                      # ポータルアプリ
│   ├── __init__.py
│   ├── apps.py
│   ├── forms.py
│   ├── urls.py
│   └── views.py                # DashboardView (TopPage + ListLogic + Ajax)
├── notification/                # お知らせアプリ
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py               # Notification
│   ├── urls.py
│   └── views.py                # NotificationDetailView
├── approvals/                   # 承認機能アプリ
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py                # SimpleRequestForm, LocalBusinessTripRequestForm, ApproverFormSet
│   ├── models.py               # Request, SimpleRequest, LocalBusinessTripRequest, Approver, ApprovalLog
│   ├── services.py             # NotificationService (メール通知ロジック)
│   ├── urls.py                 # /approvals/ 配下のURL
│   └── views.py                # BaseRequestCreateView, SimpleRequestCreateView 等
├── templates/                   # テンプレートルート
│   ├── base.html               # 共通レイアウト (Navbar, Footer)
│   ├── accounts/
│   │   ├── login.html
│   │   └── login_sent.html
│   ├── emails/                 # メールテンプレート
│   │   ├── approval_request.txt
│   │   ├── approved.txt
│   │   ├── rejected.txt
│   │   ├── remanded.txt
│   │   ├── resubmitted.txt
│   │   ├── proxy_remanded.txt
│   │   └── withdrawn.txt
│   ├── portal/
│   │   ├── index.html          # 検索・フィルタ機能付き一覧を含む
│   │   └── partials/           # Ajax用部分テンプレート
│   │       ├── notification_list.html
│   │       └── request_list.html
│   ├── notification/
│   │   └── detail.html
│   └── approvals/
│       ├── request_form.html   # フィールド動的表示対応
│       └── request_detail.html # 申請種別による表示切替対応
├── static/                      # 静的ファイルルート
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   └── images/
└── SPECIFICATION.md             # 本仕様書
```

## **8\. 用語集**

* **CRUD (Create, Read, Update, Delete)**
  * データの基本的な操作である「作成（Create）」「読み取り（Read）」「更新（Update）」「削除（Delete）」の頭文字を取った言葉。
  * 本システムでは、通常のユーザー操作による「削除」は論理的な取り下げや無効化を指し、データベースからの物理的な削除は管理者機能（Django Admin）に限定している。
* **マジックリンク (Magic Link)**
  * パスワードの代わりに、有効期限付きの使い捨てURLをメールで送信し、それをクリックすることでログインする認証方式。
  * 本システムでは、DBにトークンを保存し、使用後に削除する「ステートフル」な実装を採用している。
* **マルチテーブル継承 (Multi-table Inheritance)**
  * Djangoのモデル継承方式の一つ。親モデルと子モデルがそれぞれ独自のデータベーステーブルを持ち、OneToOneField で暗黙的にリンクされる。
  * 共通フィールド（`Request`）と固有フィールド（`SimpleRequest`, `LocalBusinessTripRequest`）を効率的に管理できる。
* **UUID (Universally Unique Identifier)**
  * 世界中で重複しない一意な識別子。データベースの主キー（ID）として、連番（1, 2, 3...）の代わりに使用する。推測が困難であるためセキュリティ向上にも寄与する。
* **Mixin (ミキシン)**  
  * Djangoなどのクラスベースのプログラムにおいて、複数のクラスで共通する機能（権限チェックや共通フィールドなど）を提供するためのクラス。多重継承を用いて利用する。  
* **オートコンプリート (Autocomplete)**
  * ユーザーが文字を入力し始めると、データベースから候補を検索してリスト表示し、入力を補助する機能。承認者選択時のドロップダウン等で使用する。
* **悲観的ロック (Pessimistic Lock)**
  * select\_for\_update() を用いて、データを取得した時点で他からの更新をブロックする排他制御方式。
  * 本システムでは、申請番号の採番や、承認アクション時のステータス更新の整合性を保つために使用する。

## **9\. Appendix: ロードマップ (将来の拡張計画)**

本バージョン(v4.0)の実装範囲外とし、次期以降のアップデートで対応する機能。

1. **ファイル添付機能**
   * 申請時にPDF、画像、Excel等のファイルを添付し、プレビューまたはダウンロードできる機能。
2. **非同期タスクキュー (Celery \+ Redis)**
   * メール送信処理および重い集計処理のバックグラウンド実行化。
3. **海外出張・長期出張申請**
   * `Request` モデルを継承した `OverseasBusinessTripRequest` 等の追加。
4. **複雑な承認ルート**
   * 「課長承認 OR 部長承認」といったOR条件分岐や、「金額によるルート自動判定」機能。
5. **代理承認機能**
   * 承認者が長期間不在の場合に、指定された代理人が承認を行う機能。
