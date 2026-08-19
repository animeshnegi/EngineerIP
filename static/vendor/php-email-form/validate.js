
  document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('contact');
    const submitBtn = document.getElementById('submitBtn');


    // If form does not exist on this page, do nothing
    if (!form) return;

    form.addEventListener('submit', function (event) {
      // Get the math verification value
      const mathInput = document.getElementById('math_verification');
      const answer = parseInt(mathInput.value);

      // Check if answer is correct (7 + 5 = 12)
      if (answer !== 12) {
        event.preventDefault();
        alert('Incorrect answer. Please enter the correct answer for 7 + 5 = ?');
        mathInput.focus();
        return;
      }

      // If answer is correct, form will submit normally
    });
  });
  



(function () {
  "use strict";

  let forms = document.querySelectorAll('.php-email-form');

  forms.forEach(function (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();

      let thisForm = this;
      let action = thisForm.getAttribute('action');

      if (!action) {
        displayError(thisForm, 'Form action is not set.');
        return;
      }

      // Show loading
      thisForm.querySelector('.loading').classList.add('d-block');
      thisForm.querySelector('.error-message').classList.remove('d-block');
      thisForm.querySelector('.sent-message').classList.remove('d-block');

      let formData = new FormData(thisForm);

      fetch(action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
        .then(response => response.text())
        .then(data => {

          thisForm.querySelector('.loading').classList.remove('d-block');

          // 🔥 Match Flask response
          if (data.trim() === "Thankyou") {
            thisForm.querySelector('.sent-message').innerHTML =
              "Thank you! Your message has been submitted successfully.";
            thisForm.querySelector('.sent-message').classList.add('d-block');
            thisForm.reset();
          } else {
            displayError(thisForm, data);
          }
        })
        .catch(error => {
          displayError(thisForm, error);
        });
    });
  });

  function displayError(thisForm, error) {
    let errorMessage = error.message || error;

    thisForm.querySelector('.loading').classList.remove('d-block');
    thisForm.querySelector('.error-message').innerHTML ="Incorrect. Please try again.";
    thisForm.querySelector('.error-message').classList.add('d-block');
  }

})();