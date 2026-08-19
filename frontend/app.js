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

  updateSearchesUI(data);

  return data;
}


// -----------------------------------------------------------------------------
// Create search
// -----------------------------------------------------------------------------

async function createSearch(search) {
  if (!googleIdToken) {
    throw new Error(
      "Google authentication required"
    );
  }

  const response = await fetch(
    `${BFF_URL}/me/searches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${googleIdToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(search),
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
      `Failed to create search: ${response.status} ${detail}`
    );
  }

  const data = await response.json();

  console.log(
    "Search created:",
    data
  );

  return data;
}


// -----------------------------------------------------------------------------
// Search UI
// -----------------------------------------------------------------------------

function updateSearchesUI(data) {
  const searchesElement =
    document.getElementById("searches");

  if (!searchesElement) {
    return;
  }

  const searches = data.searches || [];

  if (searches.length === 0) {
    searchesElement.textContent =
      "No hay búsquedas configuradas.";

    return;
  }

  searchesElement.innerHTML = "";

  searches.forEach((search) => {
    const item =
      document.createElement("div");

    item.className =
      "border rounded p-3 mb-2";


    const title =
      document.createElement("div");

    title.className =
      "fw-semibold";

    title.textContent =
      search.location?.communes?.join(", ")
      || "Sin comunas";


    const details =
      document.createElement("div");

    details.className =
      "small text-body-secondary";

    details.textContent =
      [
        search.operation === "rent"
          ? "Arriendo"
          : search.operation === "sale"
            ? "Venta"
            : search.operation,

        search.location?.region,

        search.enabled
          ? "Activa"
          : "Inactiva",
      ]
        .filter(Boolean)
        .join(" · ");


    item.appendChild(title);
    item.appendChild(details);

    searchesElement.appendChild(item);
  });
}


// -----------------------------------------------------------------------------
// Search form
// -----------------------------------------------------------------------------

async function handleSearchSubmit(event) {
  event.preventDefault();

  const resultElement =
    document.getElementById(
      "search-form-result"
    );

  const communes = [
    ...document.querySelectorAll(
      "#search-form input[type='checkbox'][value]:checked"
    ),
  ].map(
    (input) => input.value
  );

  try {
    if (!googleIdToken) {
      throw new Error(
        "Debes iniciar sesión con Google."
      );
    }

    if (communes.length === 0) {
      throw new Error(
        "Selecciona al menos una comuna."
      );
    }

    const search = {
      enabled:
        document.getElementById(
          "search-enabled"
        ).checked,

      operation:
        document.getElementById(
          "search-operation"
        ).value,

      location: {
        region:
          document.getElementById(
            "search-region"
          ).value,

        communes,
      },
    };

    console.log(
      "Creating search:",
      search
    );

    resultElement.textContent =
      "Guardando búsqueda...";

    await createSearch(search);

    await loadSearches();

    resultElement.textContent =
      "Búsqueda guardada correctamente.";

    document.getElementById(
      "search-form"
    ).reset();

    document.getElementById(
      "search-enabled"
    ).checked = true;

    const modalElement =
      document.getElementById(
        "search-modal"
      );

    const modal =
      bootstrap.Modal.getInstance(
        modalElement
      );

    if (modal) {
      modal.hide();
    }

  } catch (error) {
    console.error(
      "Search creation failed:",
      error
    );

    resultElement.textContent =
      error.message;
  }
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

    // Mercado Libre

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


    // Search form

    const searchForm =
      document.getElementById(
        "search-form"
      );

    if (searchForm) {
      searchForm.addEventListener(
        "submit",
        handleSearchSubmit
      );
    }

  }
);
