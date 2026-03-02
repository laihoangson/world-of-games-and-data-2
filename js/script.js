// Function to open games
function openGame(gameFile) {
    window.open(gameFile, '_blank');
}

// Search functionality
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('.search-input');
    
    if (searchInput) {
        searchInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                const searchTerm = this.value.toLowerCase();
                
                if (searchTerm.length > 0) {
                    // Simple search - redirect to appropriate page based on keyword
                    if (searchTerm.includes('game') || searchTerm.includes('play')) {
                        window.location.href = 'games.html';
                    } else if (searchTerm.includes('about') || searchTerm.includes('son')) {
                        window.location.href = 'about.html';
                    } else if (searchTerm.includes('intro') || searchTerm.includes('guide')) {
                        window.location.href = 'introduction.html';
                    } else if (searchTerm.includes('analysis') || searchTerm.includes('blog')) {
                        window.location.href = 'analysis.html';
                    } else if (searchTerm.includes('home') || searchTerm.includes('main')) {
                        window.location.href = 'index.html';
                    } else {
                        alert('No results found for: ' + searchTerm);
                    }
                }
            }
        });
    }
});