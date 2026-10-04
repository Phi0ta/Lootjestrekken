console.log("Script file started loading!");

// List of names for the animation cycling effect
const NAMES = ["leon", "ninke", "vera", "judy", "iris", "mark", "david"];

// Track completion state for both lootjes
let lootje1Finished = false;
let lootje2Finished = false;

function togglePassword(id) {
    var x = document.getElementById(id);
    if (x.type === "password") {
        x.type = "text";
    } else {
        x.type = "password";
    }
}

function checkBothRolled() {
    if (lootje1Finished && lootje2Finished) {
        // Send a request to the backend to update the database
        fetch('/api/mark-rolled', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(response => {
            if (response.ok) {
                console.log("Database updated: both lootjes rolled!");
            }
        }).catch(error => {
            console.error("Failed to update rolled status:", error);
        });
    }
}

function animateSlot(spanElement, buttonToHide, targetName, isLootje1) {
    // Show the parent wrapper div by removing the "hidden" class
    var container = spanElement.closest('.trek_lootje');
    if (container) {
        container.classList.remove("hidden");
    }
    
    spanElement.classList.remove("klaar"); // reset voor het geval het al eens liep
    buttonToHide.classList.add("hidden");

    let counter = 0;
    let speed = 50; // Starting speed in milliseconds
    let totalFlips = 25; // How many names it cycles through before stopping

    function roll() {
        let randomName = NAMES[Math.floor(Math.random() * NAMES.length)];
        spanElement.textContent = randomName.charAt(0).toUpperCase() + randomName.slice(1);
        
        counter++;
        if (counter < totalFlips) {
            speed += 10;
            setTimeout(roll, speed);
        } else {
            spanElement.textContent = targetName.charAt(0).toUpperCase() + targetName.slice(1);
            
            setTimeout(function() {
                spanElement.classList.add("klaar");
                
                if (isLootje1) {
                    lootje1Finished = true;
                } else {
                    lootje2Finished = true;
                }
                checkBothRolled();
            }, 1000);
        }
    }

    roll();
}

document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM is fully loaded!");

    // Redirect buttons
    var redirect_buttons = document.querySelectorAll(".redirect_button");
    redirect_buttons.forEach(function(button) {
        button.onclick = function () {
            var targetId = this.getAttribute("data-redirect-to");
            if (targetId) {
                location.href = targetId;
            }
        };
    });

    // Reveal buttons and view toggling for already rolled lootjes
    var lootjesMenu = document.getElementById("lootjes_menu");
    var singleLootjeView = document.getElementById("single_lootje_view");
    var singleLootjeTitle = document.getElementById("single_lootje_title");
    var singleLootjeSpan = document.getElementById("single_lootje_span");
    var backButton = document.getElementById("back_button");

    var reveal_lootje1_btn = document.getElementById("reveal_lootje1_btn");
    var reveal_lootje2_btn = document.getElementById("reveal_lootje2_btn");

    if (reveal_lootje1_btn && reveal_lootje2_btn && lootjesMenu && singleLootjeView) {
        reveal_lootje1_btn.onclick = function () {
            let name = this.getAttribute("data-name");
            singleLootjeTitle.textContent = "Lootje 1 (surprise):";
            singleLootjeSpan.textContent = name.charAt(0).toUpperCase() + name.slice(1);
            
            lootjesMenu.classList.add("hidden");
            singleLootjeView.classList.remove("hidden");
        };

        reveal_lootje2_btn.onclick = function () {
            let name = this.getAttribute("data-name");
            singleLootjeTitle.textContent = "Lootje 2 (gedicht):";
            singleLootjeSpan.textContent = name.charAt(0).toUpperCase() + name.slice(1);
            
            lootjesMenu.classList.add("hidden");
            singleLootjeView.classList.remove("hidden");
        };

        if (backButton) {
            backButton.onclick = function () {
                singleLootjeView.classList.add("hidden");
                lootjesMenu.classList.remove("hidden");
            };
        }
    }

    // Slot machine animation triggers for unrolled lootjes
    var trek_lootje1_button = document.getElementById("trek_lootje1_button");
    var trek_lootje1_span = document.getElementById("trek_lootje1_span");
    var trek_lootje2_button = document.getElementById("trek_lootje2_button");
    var trek_lootje2_span = document.getElementById("trek_lootje2_span");

    if (trek_lootje1_button && trek_lootje1_span && trek_lootje2_button && trek_lootje2_span){
        trek_lootje1_button.onclick = function () {
            let target = trek_lootje1_span.getAttribute("data-target");
            animateSlot(trek_lootje1_span, trek_lootje1_button, target, true);
        };

        trek_lootje2_button.onclick = function () {
            let target = trek_lootje2_span.getAttribute("data-target");
            animateSlot(trek_lootje2_span, trek_lootje2_button, target, false);
        };
    }
});