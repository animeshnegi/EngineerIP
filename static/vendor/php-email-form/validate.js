/* Shared contact-form behaviour for the Flask website. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.php-email-form').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const loading = form.querySelector('.loading');
      const errorMessage = form.querySelector('.error-message');
      const sentMessage = form.querySelector('.sent-message');
      const submitButton = form.querySelector('[type="submit"]');
      const mathInput = form.querySelector('[name="math_verification"]');

      if (mathInput && Number.parseInt(mathInput.value, 10) !== 12) {
        showError('Please solve the verification question.', form, errorMessage);
        mathInput.focus();
        return;
      }
      if (!form.checkValidity()) {
        form.classList.add('was-validated');
        showError('Please complete the required fields.', form, errorMessage);
        return;
      }

      loading?.classList.remove('d-none');
      loading?.classList.add('d-block');
      errorMessage?.classList.remove('d-block');
      sentMessage?.classList.remove('d-block');
      if (submitButton) submitButton.disabled = true;

      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
          }
        });
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : { success: response.ok, message: await response.text() };
        if (!response.ok || !payload.success) {
          throw new Error(payload.message || 'We could not submit your request.');
        }
        if (sentMessage) {
          sentMessage.textContent = payload.message || 'Thank you. Your message has been sent.';
          sentMessage.classList.add('d-block');
        } else {
          showSuccess(payload.message || 'Thank you. Your message has been sent.', form);
        }
        form.reset();
        form.classList.remove('was-validated');
      } catch (error) {
        showError(error.message || 'Please try again.', form, errorMessage);
      } finally {
        loading?.classList.remove('d-block');
        loading?.classList.add('d-none');
        if (submitButton) submitButton.disabled = false;
      }
    });
  });

  function showError(message, form, element) {
    if (element) {
      element.textContent = message;
      element.classList.add('d-block');
    } else {
      showInlineMessage(message, form, 'alert-danger');
    }
  }

  function showSuccess(message, form) {
    showInlineMessage(message, form, 'alert-success');
  }

  function showInlineMessage(message, form, className) {
    let element = form.querySelector('.contact-feedback');
    if (!element) {
      element = document.createElement('div');
      element.className = 'contact-feedback alert';
      form.prepend(element);
    }
    element.textContent = message;
    element.classList.remove('alert-danger', 'alert-success');
    element.classList.add(className, 'is-visible');
  }
});
