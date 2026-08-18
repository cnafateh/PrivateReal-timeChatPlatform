(() => {

    const gameArea =
        document.getElementById(
            "game-area"
        );


    const startButton =
        document.getElementById(
            "start-game"
        );


    const intro =
        document.getElementById(
            "game-intro"
        );


    const scoreElement =
        document.getElementById(
            "score"
        );


    const comboElement =
        document.getElementById(
            "combo"
        );


    const bestElement =
        document.getElementById(
            "best-score"
        );


    const statusElement =
        document.getElementById(
            "game-status"
        );


    let score = 0;

    let combo = 0;

    let missed = 0;

    let running = false;

    let spawnTimer = null;

    let round = 0;


    let bestScore =
        Number(
            localStorage.getItem(
                "pulse404Best"
            ) || 0
        );


    bestElement.textContent =
        bestScore;


    function updateUI() {

        scoreElement.textContent =
            score;

        comboElement.textContent =
            `${combo}x`;

    }


    function clearSignals() {

        gameArea
            .querySelectorAll(
                ".signal"
            )
            .forEach(
                signal => signal.remove()
            );

    }


    function endGame() {

        running = false;

        clearTimeout(
            spawnTimer
        );


        clearSignals();


        statusElement.textContent =
            `Game over · ${score} points`;


        startButton.textContent =
            "Play again";


        intro.classList.remove(
            "hidden"
        );


        intro.querySelector(
            "h3"
        ).textContent =
            "Signal lost";


        intro.querySelector(
            "p"
        ).textContent =
            `Final score: ${score}`;


        if (
            score > bestScore
        ) {

            bestScore =
                score;


            localStorage.setItem(
                "pulse404Best",
                String(bestScore)
            );


            bestElement.textContent =
                bestScore;

        }

    }


    function registerMiss(
        signal
    ) {

        if (
            !running
            ||
            signal.dataset.hit === "true"
        ) {
            return;
        }


        missed += 1;

        combo = 0;

        updateUI();


        if (missed >= 3) {

            endGame();

        }

        else {

            statusElement.textContent =
                `${3 - missed} lives left`;

        }

    }


    function createSignal() {

        if (!running) {
            return;
        }


        round += 1;


        const signal =
            document.createElement(
                "button"
            );


        signal.type =
            "button";


        signal.className =
            "signal";


        signal.setAttribute(
            "aria-label",
            "Catch signal"
        );


        const size =
            Math.max(
                30,
                46 -
                Math.floor(
                    round / 8
                )
            );


        signal.style.width =
            `${size}px`;


        signal.style.height =
            `${size}px`;


        const maxX =
            Math.max(
                0,
                gameArea.clientWidth -
                size -
                20
            );


        const maxY =
            Math.max(
                0,
                gameArea.clientHeight -
                size -
                20
            );


        const x =
            10 +
            Math.random() *
            maxX;


        const y =
            10 +
            Math.random() *
            maxY;


        signal.style.left =
            `${x}px`;


        signal.style.top =
            `${y}px`;


        const lifetime =
            Math.max(
                700,
                1500 -
                round * 18
            );


        signal.style.setProperty(
            "--life",
            `${lifetime}ms`
        );


        signal.addEventListener(
            "click",
            () => {

                if (
                    !running
                    ||
                    signal.dataset.hit ===
                    "true"
                ) {
                    return;
                }


                signal.dataset.hit =
                    "true";


                combo += 1;


                const comboBonus =
                    Math.min(
                        combo,
                        10
                    );


                score +=
                    10 +
                    comboBonus;


                updateUI();


                statusElement.textContent =
                    combo >= 5
                        ? `Hot streak · ${combo}x`
                        : "Signal caught";


                signal.remove();

            }
        );


        signal.addEventListener(
            "animationend",
            () => {

                if (
                    signal.isConnected
                ) {

                    registerMiss(
                        signal
                    );


                    signal.remove();

                }

            }
        );


        gameArea.appendChild(
            signal
        );


        const nextDelay =
            Math.max(
                430,
                950 -
                round * 14
            );


        spawnTimer =
            setTimeout(
                createSignal,
                nextDelay
            );

    }


    function startGame() {

        clearTimeout(
            spawnTimer
        );


        clearSignals();


        score = 0;
        combo = 0;
        missed = 0;
        round = 0;

        running = true;


        updateUI();


        intro.classList.add(
            "hidden"
        );


        statusElement.textContent =
            "3 lives";


        startButton.textContent =
            "Restart game";


        createSignal();

    }


    startButton.addEventListener(
        "click",
        startGame
    );

})();