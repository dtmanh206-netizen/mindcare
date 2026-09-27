// ============================================================
// GLOBAL
// ============================================================

const input = document.getElementById("messageInput");
const chatBox = document.getElementById("chatBox");

let currentUser = null;
let timerInterval = null;


// ============================================================
// PAGE TITLES
// ============================================================

const pageInfo = {

    home: {
        title: "Trang chủ",
        subtitle: "Một không gian nhỏ để bạn chăm sóc chính mình."
    },

    chat: {
        title: "Trò chuyện",
        subtitle: "Bạn có thể chia sẻ bất cứ điều gì đang khiến bạn suy nghĩ."
    },

    journal: {
        title: "Nhật ký",
        subtitle: "Viết ra để lòng nhẹ hơn."
    },

    stats: {
        title: "Thống kê",
        subtitle: "Theo dõi quá trình chăm sóc bản thân."
    },

    relax: {
        title: "Thư giãn",
        subtitle: "Dành vài phút để cơ thể và tâm trí được nghỉ ngơi."
    },

    settings: {
        title: "Cài đặt",
        subtitle: "Tùy chỉnh trải nghiệm MindCare."
    }

};


// ============================================================
// INITIALIZE
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadUser();

        setupNavigation();

        if (input) {

            input.addEventListener(
                "keydown",
                function (event) {

                    if (
                        event.key === "Enter"
                        && !event.shiftKey
                    ) {

                        event.preventDefault();

                        sendMessage();
                    }

                }
            );

        }

    }
);


// ============================================================
// NAVIGATION
// ============================================================

function setupNavigation() {

    const navItems =
        document.querySelectorAll(".nav-item");

    navItems.forEach(
        function (button) {

            button.addEventListener(
                "click",
                function () {

                    const page =
                        button.dataset.page;

                    goToPage(page);

                }
            );

        }
    );
}


function goToPage(page) {

    const pages =
        document.querySelectorAll(".page");

    pages.forEach(
        function (item) {

            item.classList.remove("active");

        }
    );

    const selected =
        document.getElementById(
            "page-" + page
        );

    if (selected) {
        selected.classList.add("active");
    }


    const navItems =
        document.querySelectorAll(".nav-item");

    navItems.forEach(
        function (item) {

            item.classList.remove("active");

            if (
                item.dataset.page === page
            ) {

                item.classList.add("active");

            }

        }
    );


    if (pageInfo[page]) {

        document.getElementById(
            "pageTitle"
        ).textContent =
            pageInfo[page].title;

        document.getElementById(
            "pageSubtitle"
        ).textContent =
            pageInfo[page].subtitle;

    }


    if (page === "journal") {
        loadJournals();
    }

    if (page === "stats") {
        loadStats();
    }

    if (page === "settings") {
        updateSettings();
    }

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ============================================================
// USER
// ============================================================

async function loadUser() {

    try {

        const response =
            await fetch("/api/me");

        const data =
            await response.json();

        if (data.logged_in) {

            currentUser =
                data.user;

            updateUserUI();

        }

    } catch (error) {

        console.error(
            "USER ERROR:",
            error
        );

    }

}


function updateUserUI() {

    if (!currentUser) {
        return;
    }

    const name =
        currentUser.name;

    const email =
        currentUser.email;


    const accountName =
        document.getElementById(
            "accountName"
        );

    const accountEmail =
        document.getElementById(
            "accountEmail"
        );

    const heroName =
        document.getElementById(
            "heroName"
        );

    const loginButton =
        document.getElementById(
            "loginButton"
        );

    const logoutButton =
        document.getElementById(
            "logoutButton"
        );


    if (accountName) {
        accountName.textContent = name;
    }

    if (accountEmail) {
        accountEmail.textContent = email;
    }

    if (heroName) {
        heroName.textContent =
            name.split(" ").pop();
    }

    if (loginButton) {
        loginButton.classList.add("hidden");
    }

    if (logoutButton) {
        logoutButton.classList.remove("hidden");
    }

    updateSettings();
}


// ============================================================
// CHAT
// ============================================================

function addMessage(
    message,
    type
) {

    if (!chatBox) {
        return;
    }

    const div =
        document.createElement("div");

    div.className =
        "message " + type;


    if (type === "bot") {

        div.innerHTML = `
            <div class="avatar">
                💚
            </div>

            <div class="bubble"></div>
        `;

        div.querySelector(
            ".bubble"
        ).textContent = message;

    } else {

        div.innerHTML = `
            <div class="bubble"></div>
        `;

        div.querySelector(
            ".bubble"
        ).textContent = message;

    }


    chatBox.appendChild(div);

    chatBox.scrollTop =
        chatBox.scrollHeight;

}


async function sendMessage() {

    if (!input) {
        return;
    }

    const message =
        input.value.trim();

    if (!message) {
        return;
    }


    addMessage(
        message,
        "user"
    );

    input.value = "";


    const botDiv =
        document.createElement("div");

    botDiv.className =
        "message bot";

    botDiv.innerHTML = `
        <div class="avatar">
            💚
        </div>

        <div class="bubble">
            <span>
                MindCare đang trả lời...
            </span>
        </div>
    `;


    chatBox.appendChild(botDiv);

    chatBox.scrollTop =
        chatBox.scrollHeight;


    const bubble =
        botDiv.querySelector(
            ".bubble"
        );


    const sendButton =
        document.getElementById(
            "sendButton"
        );


    if (sendButton) {
        sendButton.disabled = true;
        sendButton.textContent = "...";
    }


    try {

        const response =
            await fetch(
                "/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message: message
                    })
                }
            );


        if (!response.ok) {
            throw new Error(
                "Server error"
            );
        }


        if (!response.body) {
            throw new Error(
                "Streaming not supported"
            );
        }


        bubble.textContent = "";


        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder(
                "utf-8"
            );

        let fullText = "";


        while (true) {

            const result =
                await reader.read();

            if (result.done) {
                break;
            }


            const chunk =
                decoder.decode(
                    result.value,
                    {
                        stream: true
                    }
                );


            fullText += chunk;

            bubble.textContent =
                fullText;


            chatBox.scrollTop =
                chatBox.scrollHeight;

        }


    } catch (error) {

        console.error(
            "CHAT ERROR:",
            error
        );


        bubble.textContent =
            "MindCare không kết nối được " +
            "với máy chủ. Bạn thử lại nhé 💚";

    } finally {

        if (sendButton) {

            sendButton.disabled =
                false;

            sendButton.textContent =
                "Gửi";
        }

    }

}


// ============================================================
// MOOD
// ============================================================

function selectMood(mood) {

    if (!currentUser) {

        showToast(
            "Bạn cần đăng nhập để lưu cảm xúc 💚"
        );

        setTimeout(
            function () {
                window.location.href =
                    "/login";
            },
            1000
        );

        return;
    }


    saveMood(mood);

}


async function saveMood(mood) {

    try {

        const response =
            await fetch(
                "/api/mood",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        mood: mood
                    })
                }
            );


        const data =
            await response.json();


        if (data.success) {

            showToast(
                "Đã lưu cảm xúc hôm nay 💚"
            );

            document.getElementById(
                "page-home"
            );

        } else {

            showToast(
                data.error ||
                "Không thể lưu cảm xúc."
            );

        }

    } catch (error) {

        showToast(
            "Có lỗi xảy ra."
        );

    }

}


function closeMood() {

    const moodCard =
        document.querySelector(
            ".mood-card"
        );

    if (moodCard) {

        moodCard.style.display =
            "none";

    }

}


// ============================================================
// JOURNAL
// ============================================================

function openJournalModal() {

    if (!currentUser) {

        showToast(
            "Bạn cần đăng nhập để viết nhật ký 💚"
        );

        setTimeout(
            function () {
                window.location.href =
                    "/login";
            },
            1000
        );

        return;
    }


    document.getElementById(
        "journalModal"
    ).classList.remove("hidden");

}


function closeJournalModal() {

    document.getElementById(
        "journalModal"
    ).classList.add("hidden");

}


async function saveJournal() {

    const title =
        document.getElementById(
            "journalTitle"
        ).value.trim();


    const content =
        document.getElementById(
            "journalContent"
        ).value.trim();


    const mood =
        document.getElementById(
            "journalMood"
        ).value;


    if (!content) {

        showToast(
            "Hãy viết nội dung nhật ký trước nhé."
        );

        return;
    }


    try {

        const response =
            await fetch(
                "/api/journal",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        title: title,
                        content: content,
                        mood: mood
                    })
                }
            );


        const data =
            await response.json();


        if (data.success) {

            showToast(
                "Đã lưu nhật ký 📔"
            );


            document.getElementById(
                "journalTitle"
            ).value = "";


            document.getElementById(
                "journalContent"
            ).value = "";


            document.getElementById(
                "journalMood"
            ).value = "";


            closeJournalModal();

            loadJournals();

        } else {

            showToast(
                data.error ||
                "Không thể lưu nhật ký."
            );

        }

    } catch (error) {

        console.error(error);

        showToast(
            "Có lỗi khi lưu nhật ký."
        );

    }

}


async function loadJournals() {

    if (!currentUser) {

        showLoginRequired(
            "journalList"
        );

        return;
    }


    try {

        const response =
            await fetch(
                "/api/journals"
            );


        if (!response.ok) {
            return;
        }


        const data =
            await response.json();


        const list =
            document.getElementById(
                "journalList"
            );


        if (
            !data.journals ||
            data.journals.length === 0
        ) {

            list.innerHTML = `
                <div class="empty-state">
                    <div>📔</div>
                    <h3>Chưa có nhật ký</h3>
                    <p>
                        Hãy viết lại những điều
                        bạn đang cảm thấy hôm nay.
                    </p>
                </div>
            `;

            return;
        }


        list.innerHTML =
            data.journals
                .map(
                    function (journal) {

                        return `
                            <div class="journal-card">

                                <button
                                    class="delete-journal"
                                    onclick="deleteJournal(${journal.id})"
                                >
                                    Xóa
                                </button>

                                <h3>
                                    ${
                                        escapeHTML(
                                            journal.title ||
                                            "Nhật ký của tôi"
                                        )
                                    }
                                </h3>

                                <div class="journal-date">
                                    ${formatDate(
                                        journal.created_at
                                    )}
                                </div>

                                <div class="journal-content">
                                    ${
                                        escapeHTML(
                                            journal.content
                                        )
                                    }
                                </div>

                                ${
                                    journal.mood
                                    ?
                                    `
                                    <span class="journal-mood">
                                        ${escapeHTML(
                                            journal.mood
                                        )}
                                    </span>
                                    `
                                    :
                                    ""
                                }

                            </div>
                        `;

                    }
                )
                .join("");

    } catch (error) {

        console.error(
            "JOURNAL LOAD ERROR:",
            error
        );

    }

}


async function deleteJournal(id) {

    if (
        !confirm(
            "Bạn có chắc muốn xóa nhật ký này?"
        )
    ) {
        return;
    }


    try {

        await fetch(
            "/api/journal/" + id,
            {
                method: "DELETE"
            }
        );


        showToast(
            "Đã xóa nhật ký."
        );


        loadJournals();

        loadStats();

    } catch (error) {

        showToast(
            "Không thể xóa nhật ký."
        );

    }

}


// ============================================================
// STATISTICS
// ============================================================

async function loadStats() {

    if (!currentUser) {

        document.getElementById(
            "statMood"
        ).textContent = "—";

        document.getElementById(
            "statJournal"
        ).textContent = "—";

        document.getElementById(
            "statChat"
        ).textContent = "—";

        return;
    }


    try {

        const response =
            await fetch(
                "/api/stats"
            );


        if (!response.ok) {
            return;
        }


        const data =
            await response.json();


        document.getElementById(
            "statMood"
        ).textContent =
            data.total_checkins;


        document.getElementById(
            "statJournal"
        ).textContent =
            data.total_journals;


        document.getElementById(
            "statChat"
        ).textContent =
            data.total_chats;


    } catch (error) {

        console.error(
            "STATS ERROR:",
            error
        );

    }

}


// ============================================================
// SETTINGS
// ============================================================

function updateSettings() {

    const settingsUser =
        document.getElementById(
            "settingsUser"
        );


    const settingsLogin =
        document.getElementById(
            "settingsLogin"
        );


    if (!settingsUser) {
        return;
    }


    if (currentUser) {

        settingsUser.textContent =
            currentUser.name +
            " • " +
            currentUser.email;


        if (settingsLogin) {

            settingsLogin.textContent =
                "Đã đăng nhập";

            settingsLogin.removeAttribute(
                "href"
            );

        }

    } else {

        settingsUser.textContent =
            "Bạn chưa đăng nhập";

    }

}


// ============================================================
// RELAX
// ============================================================

function startBreathing() {

    let seconds = 60;

    const timer =
        document.getElementById(
            "relaxTimer"
        );

    const number =
        document.getElementById(
            "timerNumber"
        );


    timer.classList.remove(
        "hidden"
    );

    number.textContent =
        seconds;


    clearInterval(
        timerInterval
    );


    timerInterval =
        setInterval(
            function () {

                seconds--;

                number.textContent =
                    seconds;


                if (seconds <= 0) {

                    clearInterval(
                        timerInterval
                    );

                    showToast(
                        "Bạn đã hoàn thành 1 phút thư giãn 🌿"
                    );

                }

            },
            1000
        );

}


function oneMinuteRelax() {

    startBreathing();

    showToast(
        "Hãy thả lỏng vai và hít thở thật chậm nhé 🌿"
    );

}


function stopTimer() {

    clearInterval(
        timerInterval
    );

    document.getElementById(
        "relaxTimer"
    ).classList.add(
        "hidden"
    );

}


const quotes = [

    "Bạn không cần phải hoàn hảo để trở nên đáng quý. 💚",

    "Một ngày khó khăn không có nghĩa là mọi thứ đều tệ.",

    "Hãy cho bản thân quyền được nghỉ ngơi. 🌿",

    "Bạn đang cố gắng, và điều đó đã rất đáng trân trọng.",

    "Đi từng bước nhỏ cũng là đang tiến về phía trước.",

    "Cảm xúc của bạn xứng đáng được lắng nghe."

];


function newQuote() {

    const element =
        document.getElementById(
            "positiveQuote"
        );


    const random =
        Math.floor(
            Math.random() *
            quotes.length
        );


    element.textContent =
        quotes[random];

}


// ============================================================
// THEME
// ============================================================

function toggleTheme() {

    document.body.classList.toggle(
        "dark-mode"
    );

    showToast(
        "Đã đổi giao diện."
    );

}


// ============================================================
// TOAST
// ============================================================

let toastTimeout;


function showToast(message) {

    const toast =
        document.getElementById(
            "toast"
        );


    if (!toast) {
        return;
    }


    toast.textContent =
        message;


    toast.classList.add(
        "show"
    );


    clearTimeout(
        toastTimeout
    );


    toastTimeout =
        setTimeout(
            function () {

                toast.classList.remove(
                    "show"
                );

            },
            2500
        );

}


// ============================================================
// LOGIN REQUIRED
// ============================================================

function showLoginRequired(id) {

    const element =
        document.getElementById(id);


    if (!element) {
        return;
    }


    element.innerHTML = `
        <div class="empty-state">

            <div>🔐</div>

            <h3>
                Bạn chưa đăng nhập
            </h3>

            <p>
                Đăng nhập để sử dụng chức năng này.
            </p>

            <a
                href="/login"
                class="primary-btn"
                style="display:inline-block;text-decoration:none;"
            >
                Đăng nhập
            </a>

        </div>
    `;

}


// ============================================================
// FORMAT DATE
// ============================================================

function formatDate(dateString) {

    if (!dateString) {
        return "";
    }


    const date =
        new Date(
            dateString.replace(
                " ",
                "T"
            )
        );


    if (isNaN(date.getTime())) {
        return dateString;
    }


    return date.toLocaleString(
        "vi-VN",
        {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        }
    );

}


// ============================================================
// ESCAPE HTML
// ============================================================

function escapeHTML(text) {

    if (text === null ||
        text === undefined) {

        return "";

    }


    return String(text)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}