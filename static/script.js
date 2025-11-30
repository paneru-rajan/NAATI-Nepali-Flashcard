document.addEventListener('DOMContentLoaded', () => {
    const cardElement = document.getElementById('card');
    const overlayKnown = document.querySelector('.overlay-known');
    const overlayUnknown = document.querySelector('.overlay-unknown');
    
    // API State
    let currentCardData = null;
    let isFinished = false;

    // Load initial data
    fetchNextCard();
    updateStats();

    // --- Inputs & Controls ---
    document.getElementById('btn-flip').addEventListener('click', flipCard);
    document.getElementById('btn-known').addEventListener('click', () => handleChoice('known'));
    document.getElementById('btn-unknown').addEventListener('click', () => handleChoice('unknown'));
    
    cardElement.addEventListener('click', (e) => {
        if (!isDragging) flipCard();
    });

    document.addEventListener('keydown', (e) => {
        if (isFinished) return;
        if (e.code === 'Space') flipCard();
        if (e.code === 'ArrowRight') handleChoice('known');
        if (e.code === 'ArrowLeft') handleChoice('unknown');
    });

    // --- Swipe Logic ---
    let startX = 0;
    let currentX = 0;
    let isDragging = false;
    let hasMoved = false;

    cardElement.addEventListener('touchstart', dragStart);
    cardElement.addEventListener('mousedown', dragStart);

    cardElement.addEventListener('touchmove', dragMove);
    document.addEventListener('mousemove', dragMove);

    cardElement.addEventListener('touchend', dragEnd);
    document.addEventListener('mouseup', dragEnd);
    
    // Fix: Only flip if we haven't dragged significantly
    cardElement.addEventListener('click', (e) => {
        if (!isDragging && !hasMoved) flipCard();
    });

    function dragStart(e) {
        if (isFinished) return;
        startX = (e.type === 'touchstart') ? e.touches[0].clientX : e.clientX;
        isDragging = true;
        hasMoved = false; // Reset movement flag
        cardElement.style.transition = 'none';
    }

    function dragMove(e) {
        if (!isDragging) return;
        // Don't prevent default immediately if using touch-action in CSS, 
        // but here we want to be sure.
        // e.preventDefault(); 

        currentX = (e.type === 'touchmove') ? e.touches[0].clientX : e.clientX;
        const deltaX = currentX - startX;
        
        if (Math.abs(deltaX) > 5) hasMoved = true;

        const rotate = deltaX * 0.1;
        const isFlipped = cardElement.classList.contains('is-flipped');
        const flipRotate = isFlipped ? 'rotateY(180deg)' : '';
        
        cardElement.style.transform = `translateX(${deltaX}px) rotate(${rotate}deg) ${flipRotate}`;

        const opacity = Math.min(Math.abs(deltaX) / 100, 1);
        if (deltaX > 0) {
            overlayKnown.style.opacity = opacity;
            overlayUnknown.style.opacity = 0;
        } else {
            overlayUnknown.style.opacity = opacity;
            overlayKnown.style.opacity = 0;
        }
    }

    function dragEnd(e) {
        if (!isDragging) return;
        isDragging = false;
        
        const deltaX = currentX - startX;
        const threshold = 100;

        cardElement.style.transition = 'transform 0.4s ease';

        if (deltaX > threshold) {
            animateOut(500);
            setTimeout(() => handleChoice('known', true), 200);
        } else if (deltaX < -threshold) {
            animateOut(-500);
            setTimeout(() => handleChoice('unknown', true), 200);
        } else {
            resetCardVisuals();
        }
        // Note: hasMoved stays true here if they moved, preventing the 'click' event from flipping
        setTimeout(() => { hasMoved = false; }, 100); 
    }

    // --- Core Functions ---

    function animateOut(moveX) {
        cardElement.style.transform = `translateX(${moveX}px) rotate(${moveX * 0.1}deg)`;
        overlayKnown.style.opacity = 0;
        overlayUnknown.style.opacity = 0;
    }

    function resetCardVisuals() {
        const isFlipped = cardElement.classList.contains('is-flipped');
        cardElement.style.transform = isFlipped ? 'rotateY(180deg)' : '';
        overlayKnown.style.opacity = 0;
        overlayUnknown.style.opacity = 0;
    }

    function flipCard() {
        cardElement.classList.toggle('is-flipped');
    }

    function handleChoice(status, skipAnimation = false) {
        if (isFinished || !currentCardData) return;

        if (!skipAnimation) {
            const moveX = status === 'known' ? 500 : -500;
            animateOut(moveX);
        }

        fetch('/api/mark_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vocab_id: currentCardData.id,
                status: status
            })
        });

        setTimeout(() => {
            // UX Fix: Clear content while loading to prevent "flash of old content"
            document.getElementById('front-main').textContent = '...';
            document.getElementById('front-sub').textContent = '';
            document.getElementById('back-main').textContent = '...';
            document.getElementById('back-sub').textContent = '';

            cardElement.style.transition = 'none';
            cardElement.classList.remove('is-flipped');
            cardElement.style.transform = 'translate(0px, 0px)';
            void cardElement.offsetWidth;
            cardElement.style.transition = 'transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1)';
            
            fetchNextCard();
            updateStats();
        }, 300);
    }

    function fetchNextCard() {
        fetch('/api/get_card')
            .then(res => res.json())
            .then(data => {
                if (data.finished) {
                    showFinishedScreen();
                    return;
                }
                currentCardData = data;
                renderCard(data);
            });
    }
    
    function renderCard(data) {
        const frontLabel = document.getElementById('front-label');
        const frontMain = document.getElementById('front-main');
        const frontSub = document.getElementById('front-sub');
        
        const backLabel = document.getElementById('back-label');
        const backMain = document.getElementById('back-main');
        const backSub = document.getElementById('back-sub');

        // Logic for Bidirectional Cards
        if (data.direction === 'en_to_ne') {
            // Forward: English Front -> Nepali Back
            frontLabel.textContent = 'English';
            frontMain.textContent = data.english;
            frontSub.textContent = ''; // Empty sub for English

            backLabel.textContent = 'Nepali';
            backMain.textContent = data.nepali_roman;
            backSub.textContent = data.nepali_dev;
        } else {
            // Reverse: Nepali Front -> English Back
            frontLabel.textContent = 'Nepali';
            frontMain.textContent = data.nepali_roman;
            frontSub.textContent = data.nepali_dev;

            backLabel.textContent = 'English';
            backMain.textContent = data.english;
            backSub.textContent = ''; // Empty sub for English
        }

        document.getElementById('word-id').textContent = `Topic: ${data.id}`;
    }

    function updateStats() {
        fetch('/api/stats')
            .then(res => res.json())
            .then(data => {
                const total = data.total;
                const mastered = data.known;
                const percent = total === 0 ? 0 : Math.round((mastered / total) * 100);
                
                // Updated Format: 2 Mastered / 9 To Review / XX Total
                document.getElementById('progress-text').textContent = 
                    `${mastered} Mastered / ${data.unknown} To Review / ${total} Total`;
                
                document.getElementById('progress-bar').style.width = `${percent}%`;
            });
    }

    function showFinishedScreen() {
        isFinished = true;
        document.querySelector('.card-front').innerHTML = `
            <h2>All Done!</h2>
            <p>You've reviewed all cards.</p>
        `;
        document.querySelector('.card-back').innerHTML = `
            <h2>Great Job!</h2>
        `;
        document.querySelector('.controls').style.display = 'none';
    }
});