const form = document.getElementById("loginForm");
const messageBox = document.getElementById("msg");
const submitBtn = document.getElementById("submit-btn");
const submitIcon = document.getElementById("submit-icon");
const submitText = document.getElementById("submit-text");
const passwordInput = document.getElementById("password");
const passwordCapsWarning = document.getElementById("password-caps-warning");

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

function validate(values) {
  const fieldErrors = {
    email: "",
    password: "",
  };

  if (!values.email) fieldErrors.email = "Email is required.";
  if (!values.password) fieldErrors.password = "Password is required.";

  const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  if (values.email && !emailPattern.test(values.email)) {
    fieldErrors.email = "Please enter a valid email.";
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
      body: JSON.stringify(values),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMessage(data?.detail || "Login failed. Please check your credentials.", "error");
      return;
    }

    if (data?.access_token) {
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("token_type", data.token_type || "bearer");
    }
    setMessage("Login successful. Redirecting...", "success");
    setTimeout(() => {
      window.location.href = "/dashboard";
    }, 700);
  } catch (error) {
    setMessage("Cannot reach server. Check backend is running on port 8000.", "error");
  } finally {
    submitBtn.disabled = false;
    submitIcon.className = "fa-solid fa-right-to-bracket";
    submitText.textContent = "Log In";
  }
});

form.addEventListener("input", () => {
  renderValidation(validate(getValues()));
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
