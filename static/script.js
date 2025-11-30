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
    
    // Card tap to flip
    cardElement.addEventListener('click', (e) => {
        // Don't flip if dragging
        if (!isDragging) flipCard();
    });

    // Keyboard Shortcuts
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

    cardElement.addEventListener('touchstart', dragStart);
    cardElement.addEventListener('mousedown', dragStart);

    cardElement.addEventListener('touchmove', dragMove);
    document.addEventListener('mousemove', dragMove); // Document to catch drag outside card

    cardElement.addEventListener('touchend', dragEnd);
    document.addEventListener('mouseup', dragEnd);

    function dragStart(e) {
        if (isFinished) return;
        startX = (e.type === 'touchstart') ? e.touches[0].clientX : e.clientX;
        isDragging = true;
        cardElement.style.transition = 'none'; // Disable transition for direct follow
    }

    function dragMove(e) {
        if (!isDragging) return;
        e.preventDefault(); // Prevent scrolling

        currentX = (e.type === 'touchmove') ? e.touches[0].clientX : e.clientX;
        const deltaX = currentX - startX;
        
        // Rotate slightly while dragging
        const rotate = deltaX * 0.1;
        
        // Keep flipped state if it was flipped
        const isFlipped = cardElement.classList.contains('is-flipped');
        const flipRotate = isFlipped ? 'rotateY(180deg)' : '';
        
        cardElement.style.transform = `translateX(${deltaX}px) rotate(${rotate}deg) ${flipRotate}`;

        // Show overlays opacity based on drag distance
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
        const threshold = 100; // Pixels to trigger swipe

        cardElement.style.transition = 'transform 0.4s ease'; // Re-enable transition

        if (deltaX > threshold) {
            // Swiped Right
            animateOut(500);
            setTimeout(() => handleChoice('known', true), 200);
        } else if (deltaX < -threshold) {
            // Swiped Left
            animateOut(-500);
            setTimeout(() => handleChoice('unknown', true), 200);
        } else {
            // Reset position
            resetCardVisuals();
        }
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

        // If triggered by button/keyboard, do a small animation
        if (!skipAnimation) {
            const moveX = status === 'known' ? 500 : -500;
            animateOut(moveX);
        }

        // Send to backend
        fetch('/api/mark_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vocab_id: currentCardData.id,
                status: status
            })
        });

        // Load next
        setTimeout(() => {
            cardElement.style.transition = 'none';
            cardElement.classList.remove('is-flipped');
            cardElement.style.transform = 'translate(0px, 0px)';
            
            // Force reflow
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
        document.getElementById('word-english').textContent = data.english;
        document.getElementById('word-nepali-roman').textContent = data.nepali_roman;
        document.getElementById('word-nepali-dev').textContent = data.nepali_dev;
        document.getElementById('word-id').textContent = `Topic: ${data.id}`;
    }

    function updateStats() {
        fetch('/api/stats')
            .then(res => res.json())
            .then(data => {
                const total = data.total;
                const mastered = data.known;
                const percent = total === 0 ? 0 : Math.round((mastered / total) * 100);
                
                document.getElementById('progress-text').textContent = 
                    `${mastered} Mastered / ${data.unknown} To Review`;
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