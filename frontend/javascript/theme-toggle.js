(() => {
  const THEME_KEY = "scmTheme";

  const stylesheet = document.getElementById("theme-stylesheet");
  const toggleBtn = document.getElementById("theme-toggle");
  if (!stylesheet || !toggleBtn) return;
  const LIGHT_HREF = stylesheet.dataset.lightHref || "/css/signup.css";
  const DARK_HREF = stylesheet.dataset.darkHref || "/css/signup-dark.css";

  const urlTheme = new URLSearchParams(window.location.search).get("theme");
  const storedTheme = localStorage.getItem(THEME_KEY) || localStorage.getItem("signupTheme");
  const initialTheme =
    (urlTheme === "dark" || urlTheme === "light" ? urlTheme : null) ||
    storedTheme ||
    "light";

  function applyTheme(theme) {
    const isDark = theme === "dark";
    stylesheet.setAttribute("href", isDark ? DARK_HREF : LIGHT_HREF);
    toggleBtn.textContent = isDark ? "Light Mode" : "Dark Mode";
    localStorage.setItem(THEME_KEY, isDark ? "dark" : "light");
  }

  toggleBtn.addEventListener("click", () => {
    const nowDark = (localStorage.getItem(THEME_KEY) || initialTheme) === "dark";
    applyTheme(nowDark ? "light" : "dark");
  });

  applyTheme(initialTheme);
})();
