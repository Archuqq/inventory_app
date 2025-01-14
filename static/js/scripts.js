document.addEventListener('DOMContentLoaded', function() {
    
    const tableRows = document.querySelectorAll('.table-custom tbody tr');
    tableRows.forEach((row, index) => {
        row.style.animation = `slideIn 0.3s ease-out ${index * 0.1}s both`;
    });

    
    const statusCells = document.querySelectorAll('td:has(span[class*="text-"])');
    statusCells.forEach(cell => {
        const statusSpan = cell.querySelector('span');
        if (statusSpan) {
            const status = statusSpan.textContent.trim();
            let icon = '';
            let className = 'status-badge ';

            switch (status) {
                case 'на рассмотрении':
                    icon = '<i class="fas fa-clock"></i>';
                    className += 'status-pending';
                    break;
                case 'одобрено':
                case 'в процессе':
                    icon = '<i class="fas fa-check-circle"></i>';
                    className += 'status-approved';
                    break;
                case 'отклонено':
                    icon = '<i class="fas fa-times-circle"></i>';
                    className += 'status-rejected';
                    break;
            }

            statusSpan.className = className;
            statusSpan.innerHTML = `${icon} ${status}`;
        }
    });

    
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        const title = btn.textContent.trim();
        btn.setAttribute('data-bs-toggle', 'tooltip');
        btn.setAttribute('data-bs-placement', 'top');
        btn.setAttribute('title', title);
    });

    
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    
    const importantElements = document.querySelectorAll('.btn-primary, .btn-danger');
    importantElements.forEach(element => {
        element.addEventListener('mouseover', function() {
            this.style.transform = 'scale(1.05)';
        });
        element.addEventListener('mouseout', function() {
            this.style.transform = 'scale(1)';
        });
    });
});