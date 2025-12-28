document.addEventListener('DOMContentLoaded', function() {
    const addButton = document.getElementById('add-approver');
    const tableBody = document.querySelector('#approver-table tbody');
    const totalFormsInput = document.getElementById('id_approvers-TOTAL_FORMS');
    const maxFormsInput = document.getElementById('id_approvers-MAX_NUM_FORMS');
    
    // 空のフォームテンプレート（Djangoが出力するもの）
    // id_approvers-__prefix__-... となっている部分を置換して使う
    const emptyFormHtml = document.getElementById('empty-form-template').innerHTML;

    function updateOrders() {
        const rows = tableBody.querySelectorAll('tr.approver-row');
        rows.forEach((row, index) => {
            // 表示上の順序更新
            const orderCell = row.querySelector('.order-number');
            if (orderCell) {
                orderCell.textContent = index + 1;
            }
            // 隠しフィールドのorder更新
            const orderInput = row.querySelector('input[name$="-order"]');
            if (orderInput) {
                orderInput.value = index + 1;
            }
        });
    }

    addButton.addEventListener('click', function() {
        const currentFormCount = parseInt(totalFormsInput.value);
        const maxForms = parseInt(maxFormsInput.value);

        if (currentFormCount >= maxForms) {
            alert('これ以上承認者を追加できません。');
            return;
        }

        // 新しいフォームのHTMLを作成
        // __prefix__ を現在のフォーム数（インデックス）に置換
        const newFormHtml = emptyFormHtml.replace(/__prefix__/g, currentFormCount);
        
        // TR要素として追加
        const newRow = document.createElement('tr');
        newRow.className = 'approver-row';
        newRow.innerHTML = newFormHtml;
        
        tableBody.appendChild(newRow);

        // TOTAL_FORMSを更新
        totalFormsInput.value = currentFormCount + 1;

        // DAL (Autocomplete) の初期化
        // 新しく追加された要素内のスクリプトを実行するか、DALのイベントを発火させる必要がある
        // yl.registerFunction があればそれを使うのが一般的だが、
        // Django Admin の addRelated のように、追加された要素に対して初期化を行う。
        // dal の v3 系では DOMContentLoaded で自動初期化されるが、動的追加時は手動呼び出しが必要。
        // ここでは単純に window.dispatchEvent(new Event('load')) を呼ぶ荒技もあるが、
        // dal が document.bind('DOMNodeInserted') を監視している場合もある。
        // 一旦、dal の初期化イベントをトリガーしてみる。
        if (window.yl && window.yl.registerFunction) {
             // dal 3.x series
             // yl.registerFunction() はロード時に走るもの。
             // ここでは個別に初期化したい。
             // $(newRow).trigger('DOMNodeInserted'); // jQuery依存
             $(document).trigger('DOMNodeInserted');
        }

        // 順序の再計算（念のため）
        updateOrders();
        
        // ボタン制御
        if (parseInt(totalFormsInput.value) >= maxForms) {
            addButton.disabled = true;
        }
    });

    // 初期表示時の順序設定
    updateOrders();
});
