/**
 * フォーム送信時のボタン制御（スピナー表示と二重送信防止）
 */
document.addEventListener("submit", function(e) {
    const form = e.target;
    let submitButton = document.activeElement;

    // Enterキー等で送信された場合、activeElementがボタンでないことがある
    if (!submitButton || (submitButton.type !== "submit" && submitButton.tagName !== "BUTTON")) {
        submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
    }

    if (submitButton) {
        // confirm() などでキャンセルされた場合は何もしない
        if (e.defaultPrevented) {
            return;
        }

        // type="button"（JSで動かす用）の場合は除外
        if (submitButton.type === "button") {
            return;
        }

        // ボタンを無効化する前に、そのボタンの名前と値を隠しフィールドで保持
        // （disabledにするとサーバーに値が飛ばなくなるため）
        if (submitButton.name) {
            const hiddenInput = document.createElement("input");
            hiddenInput.type = "hidden";
            hiddenInput.name = submitButton.name;
            hiddenInput.value = submitButton.value;
            form.appendChild(hiddenInput);
        }

        // ボタンを無効化してスピナーを表示
        // 少しだけ遅延させることで、ブラウザの標準的な送信処理との競合を避ける
        setTimeout(() => {
            submitButton.disabled = true;
            
            // スピナーの作成
            const spinner = document.createElement("span");
            spinner.className = "spinner-border spinner-border-sm me-2";
            spinner.setAttribute("role", "status");
            spinner.setAttribute("aria-hidden", "true");
            
            submitButton.prepend(spinner);
        }, 0);
    }
});
