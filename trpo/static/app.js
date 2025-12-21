// static/app.js
document.addEventListener("DOMContentLoaded", () => {
    const bookingForm = document.getElementById("booking-form");
    const startDateInput = document.getElementById("start_date");
    
    // Устанавливаем ограничения даты
    if (startDateInput) {
        const today = new Date().toISOString().split('T')[0];
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 30);
        const maxDateStr = maxDate.toISOString().split('T')[0];
        
        startDateInput.min = today;
        startDateInput.max = maxDateStr;
        if (!startDateInput.value) {
            startDateInput.value = today;
        }
    }
    
    // Проверка формы бронирования
    if (bookingForm) {
        bookingForm.addEventListener("submit", (e) => {
            const roomType = document.getElementById("room_type")?.value;
            const startDate = document.getElementById("start_date")?.value;
            const durationValue = document.getElementById("duration_value")?.value;
            
            if (!roomType || !startDate || !durationValue) {
                e.preventDefault();
                alert("Заполните все поля формы!");
                return;
            }
            
            const durationNum = parseInt(durationValue);
            if (isNaN(durationNum) || durationNum <= 0) {
                e.preventDefault();
                alert("Длительность должна быть положительным числом");
                return;
            }
            
            // Проверяем дату
            const selectedDate = new Date(startDate);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            
            if (selectedDate < today) {
                e.preventDefault();
                alert("Нельзя выбирать прошедшие даты");
                return;
            }
            
            const maxDate = new Date();
            maxDate.setDate(maxDate.getDate() + 30);
            if (selectedDate > maxDate) {
                e.preventDefault();
                alert("Максимальный период бронирования - 30 дней");
                return;
            }
        });
    }
    
    // Анимация альтернатив
    const alternatives = document.querySelector(".alternatives");
    if (alternatives) {
        setTimeout(() => {
            alternatives.style.opacity = "1";
            alternatives.style.transform = "translateY(0)";
        }, 300);
    }
});