// Shared micro-interactions
document.addEventListener('DOMContentLoaded', () => {
    // Squishy button effect
    document.querySelectorAll('button, a[class*="active:scale"]').forEach(el => {
        el.addEventListener('mousedown', () => el.style.transform = 'scale(0.96)');
        el.addEventListener('mouseup', () => el.style.transform = '');
        el.addEventListener('mouseleave', () => el.style.transform = '');
    });

    // Card hover press
    document.querySelectorAll('[data-card]').forEach(card => {
        card.addEventListener('mousedown', () => card.style.transform = 'scale(0.985)');
        card.addEventListener('mouseup', () => card.style.transform = '');
        card.addEventListener('mouseleave', () => card.style.transform = '');
    });
});
