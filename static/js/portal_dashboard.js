document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('search-form');
    const notificationArea = document.getElementById('notification-area');
    const requestArea = document.getElementById('request-area');

    // Ajaxリクエストを送る関数
    async function updateList(target, params) {
        const url = new URL(window.location.href);
        url.search = params.toString();
        url.searchParams.set('target', target);

        try {
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!response.ok) throw new Error('Network response was not ok');
            
            const html = await response.text();
            if (target === 'notification') {
                notificationArea.innerHTML = html;
            } else if (target === 'request') {
                requestArea.innerHTML = html;
            }
        } catch (error) {
            console.error('Fetch error:', error);
        }
    }

    // ページネーションのクリックイベント（委譲）
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.ajax-pagination');
        if (!btn) return;

        e.preventDefault();
        const target = btn.dataset.target;
        const page = btn.dataset.page;
        
        const params = new URLSearchParams(new FormData(searchForm));
        if (target === 'notification') {
            params.set('n_page', page);
        } else {
            params.set('page', page);
        }
        
        updateList(target, params);
    });

    // 検索フォームの送信イベント
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const params = new URLSearchParams(new FormData(searchForm));
        updateList('request', params);
    });
});
