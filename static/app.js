// static/app.js

document.addEventListener("DOMContentLoaded", () => {
  const bookingForm = document.getElementById("booking-form");
  const alternatives = document.querySelector(".alternatives");

  if (bookingForm) {
    bookingForm.addEventListener("submit", (e) => {
      const roomType = document.getElementById("room_type").value;
      const startDate = document.getElementById("start_date").value;
      const durationValue = document.getElementById("duration_value").value;

      if (!roomType || !startDate || !durationValue) {
        e.preventDefault();
        alert("Заполните все поля формы!");
      }
    });
  }

  if (alternatives) {
    alternatives.style.transition = "all 0.3s ease";
    alternatives.style.borderColor = "#2f6fed";
    alternatives.style.backgroundColor = "#f0f8ff";
  }
});
