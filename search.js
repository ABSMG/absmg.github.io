document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("searchInput");
    const cards = document.querySelectorAll(".card");
    const filterButtons = document.querySelectorAll("[data-filter]");
    const noResults = document.querySelector(".no-results");

    if (!searchInput || !cards.length) return;

    let activeFilter = "all";

    function filterCards() {
        const query = searchInput.value.toLowerCase().trim();
        let visibleCards = 0;

        cards.forEach(function (card) {
            const category = (
                card.getAttribute("data-category") || ""
            ).toLowerCase();

            const searchableText = (
                card.getAttribute("data-search") ||
                card.textContent ||
                ""
            ).toLowerCase();

            const matchesSearch =
                query === "" || searchableText.includes(query);

            const categories = category
    .split(/\s+/)
    .filter(Boolean);

const matchesFilter =
    activeFilter === "all" ||
    categories.includes(activeFilter.toLowerCase());


            if (matchesSearch && matchesFilter) {
                card.style.display = "";
                visibleCards++;
            } else {
                card.style.display = "none";
            }
        });

        if (noResults) {
            noResults.style.display =
                visibleCards === 0 ? "block" : "none";
        }
    }

    searchInput.addEventListener("input", filterCards);

    filterButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            activeFilter = (
                button.getAttribute("data-filter") || "all"
            ).toLowerCase();

            filterButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");

            filterCards();
        });
    });

    filterCards();
});
