const GOOGLE_CLIENT_ID =
  "366674000591-k5n9g6vo12vrk40egcmn1ht3cnvlrciv.apps.googleusercontent.com";

const BFF_URL =
  "https://housepricing-web-bff-vyghkhukra-tl.a.run.app";

let googleIdToken = null;
let currentUser = null;


// -----------------------------------------------------------------------------
// Google Identity Services
// -----------------------------------------------------------------------------

window.onload = () => {
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
  });

  google.accounts.id.renderButton(
    document.getElementById("google-signin-button"),
    {
      theme: "outline",
      size: "large",
    }
  );
};


// -----------------------------------------------------------------------------
// Google authentication
// -----------------------------------------------------------------------------

async function handleGoogleCredential(response) {
  try {
    googleIdToken = response.credential;

    if (!googleIdToken) {
      throw new Error(
        "Google ID token not received"
      );
    }

    console.log(
      "Google authentication completed"
    );

    await loadCurrentUser();
    await loadMercadoLibreStatus();
    await loadSearches();

  } catch (error) {
    console.error(
      "Google authentication failed:",
      error
    );

    googleIdToken = null;
    currentUser = null;
  }
}


// -----------------------------------------------------------------------------
// Current Google user
// -----------------------------------------------------------------------------

async function loadCurrentUser() {
  const response = await fetch(
    `${BFF_URL}/me`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${googleIdToken}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load user: ${response.status}`
    );
  }

  const data = await response.json();

  currentUser = data.user;

  console.log(
    "Authenticated user:",
    {
      email: currentUser.email,
      name: currentUser.name,
    }
  );

  return currentUser;
}


// -----------------------------------------------------------------------------
// Mercado Libre connection status
// -----------------------------------------------------------------------------

async function loadMercadoLibreStatus() {
  if (!googleIdToken) {
    throw new Error(
      "Google authentication required"
    );
  }

  const response = await fetch(
    `${BFF_URL}/me/mercadolibre`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${googleIdToken}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load Mercado Libre status: ${response.status}`
    );
  }

  const data = await response.json();

  console.log(
    "Mercado Libre status:",
    data
  );

  updateMercadoLibreUI(data);

  return data;
}


// -----------------------------------------------------------------------------
// Mercado Libre OAuth
// -----------------------------------------------------------------------------

async function connectMercadoLibre() {
  if (!googleIdToken) {
    throw new Error(
      "Google authentication required"
    );
  }

  const response = await fetch(
    `${BFF_URL}/oauth/mercadolibre`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${googleIdToken}`,
      },
    }
  );

  if (!response.ok) {
    let detail = "";

    try {
      const error = await response.json();
      detail = JSON.stringify(error);
    } catch {
      detail = await response.text();
    }

    throw new Error(
      `Failed to start Mercado Libre OAuth: ${response.status} ${detail}`
    );
  }

  const data = await response.json();

  if (!data.authorization_url) {
    throw new Error(
      "Mercado Libre authorization URL not received"
    );
  }

  window.location.href =
    data.authorization_url;
}


// -----------------------------------------------------------------------------
// User searches
// -----------------------------------------------------------------------------

async function loadSearches() {
  if (!googleIdToken) {
    throw new Error(
      "Google authentication required"
    );
  }

  const response = await fetch(
    `${BFF_URL}/me/searches`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${googleIdToken}`,
      },
    }
  );

  if (!response.ok) {
    let detail = "";

    try {
      const error = await response.json();
      detail = JSON.stringify(error);
    } catch {
      detail = await response.text();
    }

    throw new Error(
      `Failed to load searches: ${response.status} ${detail}`
    );
  }

  const data = await response.json();

  console.log(
    "User searches:",
    data
  );

  return data;
}


// -----------------------------------------------------------------------------
// UI
// -----------------------------------------------------------------------------

function updateMercadoLibreUI(data) {
  const statusElement =
    document.getElementById(
      "mercadolibre-status"
    );

  const connectButton =
    document.getElementById(
      "mercadolibre-connect"
    );

  if (statusElement) {
    statusElement.textContent =
      data.connected
        ? "Mercado Libre: conectado"
        : "Mercado Libre: no conectado";
  }

  if (connectButton) {
    connectButton.style.display =
      data.connected
        ? "none"
        : "block";
  }
}


// -----------------------------------------------------------------------------
// UI events
// -----------------------------------------------------------------------------

document.addEventListener(
  "DOMContentLoaded",
  () => {
    const connectButton =
      document.getElementById(
        "mercadolibre-connect"
      );

    if (connectButton) {
      connectButton.addEventListener(
        "click",
        async () => {
          try {
            await connectMercadoLibre();
          } catch (error) {
            console.error(
              "Mercado Libre connection failed:",
              error
            );
          }
        }
      );
    }
  }
);
