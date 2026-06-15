function toggleProfileMenu() {
  const popup = document.getElementById("profilePopup");
  if (popup) popup.classList.toggle("open");
}

document.addEventListener("click", function (event) {
  const popup  = document.getElementById("profilePopup");
  const button = document.getElementById("profileBtn");
  if (!popup || !button) return;
  if (!popup.contains(event.target) && !button.contains(event.target)) {
    popup.classList.remove("open");
  }
});

// Helper function to handle unauthorized state cleanly
function handleUnauthorized() {
  document.body.style.setProperty("display", "none", "important");
  window.location.replace("/dash/signin.html");
}

// Back button — re-verify instead of blindly redirecting
window.addEventListener("pageshow", async (e) => {
  if (e.persisted) {
    try {
      const res = await fetch("/verify-token/", {
        method: "GET",
        credentials: "include"
      });
      if (res.status !== 200) {
        handleUnauthorized();
      }
    } catch {
      handleUnauthorized();
    }
  }
});

// Normal load — verify token with backend
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch("/verify-token/", {
      method: "GET",
      credentials: "include"
    });

    if (res.status !== 200) {
      handleUnauthorized();
      return;
    }

    // Token valid — show page and fill user info
    document.body.style.setProperty("display", "block", "important");

    const email = sessionStorage.getItem("Email");
    const name  = sessionStorage.getItem("Name");
    if (name)  document.querySelectorAll(".profile-name").forEach(el => el.textContent = name);
    if (email) {
      const userIdEl = document.getElementById("user-id");
      if (userIdEl) userIdEl.textContent = email;
    }

    // ONLY start the background interval loop AFTER successful initial verification
    startTokenInterval();

  } catch {
    handleUnauthorized();
  }
});

// Wrapped interval in a function so it only runs when authenticated
function startTokenInterval() {
  setInterval(async () => {
    try {
      const res = await fetch("/verify-token/", { method: "GET", credentials: "include" });
      if (res.status !== 200) {
        handleUnauthorized();
      }
    } catch {
      handleUnauthorized();
    }
  }, 30000); // Recheck every 30 seconds
}