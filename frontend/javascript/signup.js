const form = document.getElementById("signupForm");
const messageBox = document.getElementById("msg");
const submitBtn = document.getElementById("submit-btn");
const submitIcon = document.getElementById("submit-icon");
const submitText = document.getElementById("submit-text");
const successPanel = document.getElementById("success-panel");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");
const strengthBar = document.getElementById("strength-bar");
const strengthText = document.getElementById("strength-text");
const passwordHints = document.getElementById("password-hints");
const passwordCapsWarning = document.getElementById("password-caps-warning");
const confirmCapsWarning = document.getElementById("confirm-caps-warning");

const fields = {
  name: document.getElementById("name"),
  email: document.getElementById("email"),
  phone: document.getElementById("phone"),
  password: passwordInput,
  confirmPassword: confirmPasswordInput,
};

const errors = {
  name: document.getElementById("name-error"),
  email: document.getElementById("email-error"),
  phone: document.getElementById("phone-error"),
  password: document.getElementById("password-error"),
  confirmPassword: document.getElementById("confirmPassword-error"),
};

const passwordRuleEls = {
  length: document.getElementById("rule-length"),
  upper: document.getElementById("rule-upper"),
  lower: document.getElementById("rule-lower"),
  number: document.getElementById("rule-number"),
};
const touched = {
  name: false,
  email: false,
  phone: false,
  password: false,
  confirmPassword: false,
};
let submitted = false;

function setMessage(text, type) {
  messageBox.textContent = text;
  messageBox.className = `message ${type || ""}`.trim();
}

function showSuccessPanel(text) {
  successPanel.textContent = text;
  successPanel.classList.add("visible");
}

function hideSuccessPanel() {
  successPanel.textContent = "";
  successPanel.classList.remove("visible");
}

function setCapsWarning(visible, warningEl) {
  if (!warningEl) return;
  warningEl.classList.toggle("visible", visible);
}

function handleCapsLock(event, warningEl) {
  const capsOn = event.getModifierState && event.getModifierState("CapsLock");
  setCapsWarning(Boolean(capsOn), warningEl);
}

function getValues() {
  return {
    name: fields.name.value.trim(),
    email: fields.email.value.trim(),
    phone: fields.phone.value.replace(/\D/g, "").trim(),
    password: fields.password.value,
    confirmPassword: fields.confirmPassword.value,
  };
}

function passwordChecks(password) {
  return {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
  };
}

function getStrength(password) {
  const checks = passwordChecks(password);
  const score = Object.values(checks).filter(Boolean).length;
  if (!password) return { score: 0, label: "Too weak" };
  if (score <= 1) return { score, label: "Weak" };
  if (score <= 3) return { score, label: "Medium" };
  return { score, label: "Strong" };
}

function updateStrengthUI(password) {
  const checks = passwordChecks(password);
  passwordRuleEls.length.classList.toggle("valid", checks.length);
  passwordRuleEls.upper.classList.toggle("valid", checks.upper);
  passwordRuleEls.lower.classList.toggle("valid", checks.lower);
  passwordRuleEls.number.classList.toggle("valid", checks.number);

  const { score, label } = getStrength(password);
  const width = Math.min((score / 4) * 100, 100);
  strengthBar.style.width = `${width}%`;
  strengthText.textContent = `Strength: ${label}`;

  if (label === "Strong") {
    strengthBar.style.backgroundColor = "#22c55e";
  } else if (label === "Medium") {
    strengthBar.style.backgroundColor = "#eab308";
  } else {
    strengthBar.style.backgroundColor = "#ef4444";
  }
}

function updatePasswordHintsVisibility(values, validation) {
  const hasPasswordInput = values.password.length > 0;
  const passwordInvalid = Boolean(validation.fieldErrors.password);
  const shouldShow = hasPasswordInput && (touched.password || submitted || passwordInvalid);
  passwordHints.classList.toggle("visible", shouldShow);
}

function validate(values) {
  const { name, email, phone, password, confirmPassword } = values;
  const fieldErrors = {
    name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
  };

  if (!name || !email || !phone || !password || !confirmPassword) {
    if (!name) fieldErrors.name = "Full name is required.";
    if (!email) fieldErrors.email = "Email is required.";
    if (!phone) fieldErrors.phone = "Phone is required.";
    if (!password) fieldErrors.password = "Password is required.";
    if (!confirmPassword) fieldErrors.confirmPassword = "Please confirm password.";
  }

  const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  if (email && !emailPattern.test(email)) {
    fieldErrors.email = "Please enter a valid email.";
  }

  const phonePattern = /^\d{10}$/;
  if (phone && !phonePattern.test(phone)) {
    fieldErrors.phone = "Phone must be exactly 10 digits.";
  }

  const checks = passwordChecks(password);
  if (password && (!checks.length || !checks.upper || !checks.lower || !checks.number)) {
    fieldErrors.password = "Use 8+ chars with uppercase, lowercase, and number.";
  }

  if (password && confirmPassword && password !== confirmPassword) {
    fieldErrors.confirmPassword = "Passwords do not match.";
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
  submitBtn.disabled = !result.isValid;
  updatePasswordHintsVisibility(getValues(), result);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage("");
  hideSuccessPanel();
  submitted = true;

  const values = getValues();
  const validation = validate(values);
  renderValidation(validation);
  if (!validation.isValid) return;

  setMessage("");

  const payload = {
    name: values.name,
    email: values.email,
    phone: values.phone,
    password: values.password,
    confirm_password: values.confirmPassword,
  };

  submitBtn.disabled = true;
  submitIcon.className = "fa-solid fa-spinner fa-spin";
  submitText.textContent = "Creating...";

  try {
    const response = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data?.detail || "Signup failed. Please try again.";
      setMessage(detail, "error");
      return;
    }

    let secondsLeft = 4;
    setMessage("Signup successful.", "success");
    showSuccessPanel(`Account created successfully. Redirecting to login in ${secondsLeft}s...`);
    const timer = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        clearInterval(timer);
        window.location.href = "/login";
        return;
      }
      showSuccessPanel(`Account created successfully. Redirecting to login in ${secondsLeft}s...`);
    }, 1000);
    form.reset();
    submitted = false;
    Object.keys(touched).forEach((key) => {
      touched[key] = false;
    });
    updateStrengthUI("");
    renderValidation(validate(getValues()));
  } catch (error) {
    setMessage("Cannot reach server. Check backend is running on port 8000.", "error");
  } finally {
    submitBtn.disabled = false;
    submitIcon.className = "fa-solid fa-user-plus";
    submitText.textContent = "Sign Up";
  }
});

form.addEventListener("input", () => {
  fields.phone.value = fields.phone.value.replace(/\D/g, "").slice(0, 10);
  const values = getValues();
  updateStrengthUI(values.password);
  renderValidation(validate(values));
});

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

[passwordInput, confirmPasswordInput].forEach((input) => {
  input.addEventListener("keydown", (event) => {
    handleCapsLock(event, input.id === "password" ? passwordCapsWarning : confirmCapsWarning);
  });

  input.addEventListener("keyup", (event) => {
    handleCapsLock(event, input.id === "password" ? passwordCapsWarning : confirmCapsWarning);
  });

  input.addEventListener("blur", () => {
    setCapsWarning(false, input.id === "password" ? passwordCapsWarning : confirmCapsWarning);
  });
});

updateStrengthUI("");
renderValidation(validate(getValues()));

