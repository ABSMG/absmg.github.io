
document.addEventListener("DOMContentLoaded", function () {

    const searchInput = document.getElementById("searchInput");
    const cards = document.querySelectorAll(".opportunity-card");
    const resultCount = document.getElementById("resultCount");

    if (!searchInput || !cards.length) {
        return;
    }

    function performSearch() {

        const query = searchInput.value
            .toLowerCase()
            .trim();

        let visibleCards = 0;

        cards.forEach(function (card) {

            const searchableText = card.textContent
                .toLowerCase();

            if (query === "" || searchableText.includes(query)) {

                card.style.display = "";

                visibleCards++;

            } else {

                card.style.display = "none";

            }

        });

        if (query === "") {

            resultCount.textContent = "";

        } else if (visibleCards === 0) {

            resultCount.textContent =
                "No matching opportunities found.";

        } else {

            resultCount.textContent =
                visibleCards +
                " matching " +
                (visibleCards === 1 ? "opportunity" : "opportunities") +
                " found.";

        }

    }

    searchInput.addEventListener("input", performSearch);

});
