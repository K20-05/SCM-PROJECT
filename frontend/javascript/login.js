const form = document.getElementById("loginForm");
const messageBox = document.getElementById("msg");
const submitBtn = document.getElementById("submit-btn");
const submitIcon = document.getElementById("submit-icon");
const submitText = document.getElementById("submit-text");
const passwordInput = document.getElementById("password");
const passwordCapsWarning = document.getElementById("password-caps-warning");
const captchaGroup = document.getElementById("captcha-group");
const googleCaptcha = document.getElementById("google-captcha");
const localCaptcha = document.getElementById("local-captcha");
const captchaQuestion = document.getElementById("captcha-question");
const captchaAnswer = document.getElementById("captcha-answer");
const captchaRefresh = document.getElementById("captcha-refresh");
const captchaError = document.getElementById("captcha-error");

const fields = {
  email: document.getElementById("email"),
  password: passwordInput,
};

const errors = {
  email: document.getElementById("email-error"),
  password: document.getElementById("password-error"),
};

const touched = {
  email: false,
  password: false,
};

let submitted = false;
let captchaProvider = "local";
let captchaId = "";
let recaptchaWidgetId = null;

function setMessage(text, type) {
  messageBox.textContent = text;
  messageBox.className = `message ${type || ""}`.trim();
}

function setCapsWarning(visible) {
  if (!passwordCapsWarning) return;
  passwordCapsWarning.classList.toggle("visible", visible);
}

function getValues() {
  return {
    email: fields.email.value.trim(),
    password: fields.password.value,
  };
}

function captchaPayload() {
  if (captchaProvider === "google") {
    return {
      recaptcha_token: window.grecaptcha && recaptchaWidgetId !== null
        ? window.grecaptcha.getResponse(recaptchaWidgetId)
        : "",
    };
  }
  return {
    captcha_id: captchaId,
    captcha_answer: captchaAnswer.value.trim(),
  };
}

function validate(values) {
  const fieldErrors = {
    email: "",
    password: "",
    captcha: "",
  };

  if (!values.email) fieldErrors.email = "Email is required.";
  if (!values.password) fieldErrors.password = "Password is required.";

  const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  if (values.email && !emailPattern.test(values.email)) {
    fieldErrors.email = "Please enter a valid email.";
  }
  if (captchaProvider === "google") {
    const token = window.grecaptcha && recaptchaWidgetId !== null
      ? window.grecaptcha.getResponse(recaptchaWidgetId)
      : "";
    if (!token) fieldErrors.captcha = "Please complete the CAPTCHA.";
  } else if (!captchaAnswer.value.trim()) {
    fieldErrors.captcha = "CAPTCHA answer is required.";
  }

  const isValid = Object.values(fieldErrors).every((msg) => !msg);
  return { isValid, fieldErrors };
}

function renderValidation(result) {
  Object.entries(errors).forEach(([key, el]) => {
    const msg = result.fieldErrors[key] || "";
    const show = submitted || touched[key];
    el.textContent = show ? msg : "";
    fields[key].classList.toggle("invalid", show && Boolean(msg));
  });
  captchaError.textContent = submitted ? result.fieldErrors.captcha || "" : "";
  captchaAnswer?.classList.toggle("invalid", submitted && Boolean(result.fieldErrors.captcha));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage("");
  submitted = true;

  const values = getValues();
  const validation = validate(values);
  renderValidation(validation);
  if (!validation.isValid) return;

  submitBtn.disabled = true;
  submitIcon.className = "fa-solid fa-spinner fa-spin";
  submitText.textContent = "Logging in...";

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...values, ...captchaPayload() }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const fallbackMessage = response.status >= 500
        ? "Authentication service is unavailable. Please check the database connection."
        : "Login failed. Please check your credentials.";
      setMessage(data?.detail || fallbackMessage, "error");
      resetCaptcha();
      return;
    }

    if (!data?.access_token) {
      setMessage("Login succeeded but no session token was returned.", "error");
      return;
    }

    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("user_role");
    localStorage.removeItem("dashboard_url");
    sessionStorage.setItem("access_token", data.access_token);
    sessionStorage.setItem("token_type", data.token_type || "bearer");
    if (data.role) sessionStorage.setItem("user_role", data.role);
    if (data.dashboard_url) sessionStorage.setItem("dashboard_url", data.dashboard_url);

    setMessage("Login successful. Redirecting...", "success");
    setTimeout(() => {
      window.location.replace(data?.dashboard_url || "/dashboard");
    }, 700);
  } catch (error) {
    setMessage("Cannot reach server. Check backend is running on port 8000.", "error");
    resetCaptcha();
  } finally {
    submitBtn.disabled = false;
    submitIcon.className = "fa-solid fa-right-to-bracket";
    submitText.textContent = "Log In";
  }
});

form.addEventListener("input", () => {
  renderValidation(validate(getValues()));
});

captchaRefresh?.addEventListener("click", loadLocalCaptcha);

Object.entries(fields).forEach(([key, input]) => {
  input.addEventListener("blur", () => {
    touched[key] = true;
    renderValidation(validate(getValues()));
  });
});

document.querySelectorAll(".toggle-password").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.getAttribute("data-target");
    const input = document.getElementById(targetId);
    const icon = btn.querySelector("i");
    if (!input || !icon) return;
    const isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";
    icon.className = isPassword ? "fa-regular fa-eye-slash" : "fa-regular fa-eye";
  });
});

passwordInput.addEventListener("keydown", (event) => {
  const capsOn = event.getModifierState && event.getModifierState("CapsLock");
  setCapsWarning(Boolean(capsOn));
});

passwordInput.addEventListener("keyup", (event) => {
  const capsOn = event.getModifierState && event.getModifierState("CapsLock");
  setCapsWarning(Boolean(capsOn));
});

passwordInput.addEventListener("blur", () => {
  setCapsWarning(false);
});

renderValidation(validate(getValues()));
initCaptcha();

async function initCaptcha() {
  try {
    const response = await fetch("/api/auth/captcha/config");
    if (!response.ok) throw new Error("CAPTCHA config unavailable");
    const config = await response.json();
    captchaProvider = config.provider || "local";
    if (captchaProvider === "google" && config.site_key) {
      localCaptcha.hidden = true;
      loadGoogleCaptcha(config.site_key);
      return;
    }
  } catch (error) {
    captchaProvider = "local";
  }
  googleCaptcha.hidden = true;
  localCaptcha.hidden = false;
  await loadLocalCaptcha();
}

function loadGoogleCaptcha(siteKey) {
  googleCaptcha.hidden = false;
  localCaptcha.hidden = true;

  window.renderLoginCaptcha = () => {
    if (recaptchaWidgetId !== null) return;
    recaptchaWidgetId = window.grecaptcha.render("google-captcha", { sitekey: siteKey });
  };

  if (window.grecaptcha?.render) {
    window.renderLoginCaptcha();
    return;
  }
  if (document.getElementById("recaptcha-api-script")) return;

  const script = document.createElement("script");
  script.id = "recaptcha-api-script";
  script.src = "https://www.google.com/recaptcha/api.js?onload=renderLoginCaptcha&render=explicit";
  script.async = true;
  script.defer = true;
  script.onerror = () => {
    captchaError.textContent = "Could not load Google reCAPTCHA. Please refresh and try again.";
  };
  document.head.appendChild(script);
}

async function loadLocalCaptcha() {
  captchaQuestion.textContent = "Loading...";
  captchaAnswer.disabled = true;
  captchaRefresh.disabled = true;
  try {
    const response = await fetch("/api/auth/captcha");
    if (!response.ok) throw new Error("CAPTCHA unavailable");
    const data = await response.json();
    captchaId = data.captcha_id || "";
    captchaQuestion.textContent = data.question || "Refresh CAPTCHA";
    captchaAnswer.value = "";
    captchaError.textContent = "";
  } catch (error) {
    captchaId = "";
    captchaQuestion.textContent = "Not loaded";
    captchaError.textContent = "Could not load CAPTCHA.";
  } finally {
    captchaAnswer.disabled = false;
    captchaRefresh.disabled = false;
  }
}

function resetCaptcha() {
  if (captchaProvider === "google" && window.grecaptcha && recaptchaWidgetId !== null) {
    window.grecaptcha.reset(recaptchaWidgetId);
    return;
  }
  loadLocalCaptcha();
}
