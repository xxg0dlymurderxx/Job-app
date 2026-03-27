const form = document.querySelector("#job-form");
const activeGrid = document.querySelector("#listings-grid");
const closedGrid = document.querySelector("#closed-listings-grid");
const template = document.querySelector("#listing-template");
const searchInput = document.querySelector("#search");
const categoryFilter = document.querySelector("#category-filter");
const formMessage = document.querySelector("#form-message");
const listingsMessage = document.querySelector("#listings-message");
const submitButton = form.querySelector('button[type="submit"]');
const jobViewTitle = document.querySelector("#job-view-title");
const jobViewCategory = document.querySelector("#job-view-category");
const jobViewStatus = document.querySelector("#job-view-status");
const jobViewPay = document.querySelector("#job-view-pay");
const jobViewDescription = document.querySelector("#job-view-description");
const jobViewLocation = document.querySelector("#job-view-location");
const jobViewDeadline = document.querySelector("#job-view-deadline");
const jobViewContact = document.querySelector("#job-view-contact");
const jobViewEmail = document.querySelector("#job-view-email");
const jobViewPhone = document.querySelector("#job-view-phone");
const jobViewClose = document.querySelector("#job-view-close");
const jobMessageForm = document.querySelector("#job-message-form");
const jobMessageSenderName = document.querySelector("#job-message-sender-name");
const jobMessageSenderEmail = document.querySelector("#job-message-sender-email");
const jobMessageSenderContact = document.querySelector("#job-message-sender-contact");
const jobMessageBody = document.querySelector("#job-message-body");
const jobMessageStatus = document.querySelector("#job-message-status");
const tabTriggers = document.querySelectorAll("[data-tab-target]");
const tabPanels = document.querySelectorAll("[data-tab-panel]");
const topbarTabs = document.querySelectorAll(".topbar-tab");
const ownerTokenStorageKey = "hirepatch-owner-tokens";

const getTodayString = () => {
  const now = new Date();
  const timezoneOffset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - timezoneOffset).toISOString().split("T")[0];
};

let listings = [];
let ownerTokens = loadOwnerTokens();
let openTabs = [];
let activeJobId = "";

const formatCurrency = (amount) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(amount);

const formatPay = (listing) => {
  const amount = formatCurrency(listing.pay);
  return listing.pay_type === "hourly" ? `${amount}/hr` : amount;
};

const formatDate = (value) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(`${value}T00:00:00`));

const setMessage = (text, tone = "") => {
  formMessage.textContent = text;
  formMessage.className = `form-message ${tone}`.trim();
};

const setListingsMessage = (text, tone = "") => {
  listingsMessage.textContent = text;
  listingsMessage.className = `listings-message ${tone}`.trim();
};

const setJobMessageStatus = (text, tone = "") => {
  jobMessageStatus.textContent = text;
  jobMessageStatus.className = `form-message ${tone}`.trim();
};

function loadOwnerTokens() {
  try {
    const stored = localStorage.getItem(ownerTokenStorageKey);
    const parsed = stored ? JSON.parse(stored) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

const saveOwnerTokens = () => {
  localStorage.setItem(ownerTokenStorageKey, JSON.stringify(ownerTokens));
};

const ownsListing = (listing) => Boolean(ownerTokens[listing.id]);

const openTab = (tabName) => {
  if (!openTabs.includes(tabName)) {
    openTabs.push(tabName);
  }
};

const closeTab = (tabName) => {
  const index = openTabs.indexOf(tabName);
  if (index !== -1) {
    openTabs.splice(index, 1);
  }
};

const renderOpenTabs = () => {
  tabPanels.forEach((panel) => {
    const index = openTabs.indexOf(panel.dataset.tabPanel);
    const isActive = index !== -1;
    panel.hidden = !isActive;
    panel.classList.toggle("is-active", isActive);
    panel.style.order = isActive ? String(index) : "";
  });

  topbarTabs.forEach((tab) => {
    const isActive = openTabs.includes(tab.dataset.tabTarget);
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
  });
};

tabTriggers.forEach((trigger) => {
  trigger.addEventListener("click", () => {
    const target = trigger.dataset.tabTarget;
    if (openTabs.includes(target)) {
      closeTab(target);
    } else {
      openTab(target);
    }

    renderOpenTabs();
  });
});

const getFilteredListings = () => {
  const search = searchInput.value.trim().toLowerCase();
  const category = categoryFilter.value;

  return listings
    .slice()
    .filter((listing) => {
      const matchesCategory = category === "All" || listing.category === category;
      const haystack = [
        listing.title,
        listing.location,
        listing.description,
        listing.contact
      ]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !search || haystack.includes(search);

      return matchesCategory && matchesSearch;
    });
};

const formatClosedDate = (value) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(value));

const sortByTimestamp = (items, field) =>
  items.slice().sort((a, b) => (b[field] || 0) - (a[field] || 0));

const getListingById = (listingId) =>
  listings.find((listing) => listing.id === listingId);

const closeJobView = () => {
  activeJobId = "";
  closeTab("job");
  renderOpenTabs();
};

const renderJobView = () => {
  if (!activeJobId) {
    closeJobView();
    return;
  }

  const listing = getListingById(activeJobId);
  if (!listing || listing.closed_at) {
    closeJobView();
    return;
  }

  jobViewTitle.textContent = listing.title;
  jobViewCategory.textContent = listing.category;
  jobViewStatus.textContent = listing.status;
  jobViewStatus.classList.remove("is-closed");
  jobViewPay.textContent =
    listing.pay_type === "hourly" ? `${formatPay(listing)} rate` : `${formatPay(listing)} payout`;
  jobViewDescription.textContent = listing.description;
  jobViewLocation.textContent = listing.location;
  jobViewDeadline.textContent = formatDate(listing.deadline);
  jobViewContact.textContent = listing.contact;
  jobViewEmail.textContent = listing.email;
  jobViewPhone.textContent = listing.phone;
  setJobMessageStatus("Send will deliver your message by email and text when configured.", "");
  jobMessageForm.reset();
  openTab("job");
  renderOpenTabs();
};

const closeListingById = async (listingId) => {
  const ownerToken = ownerTokens[listingId];
  if (!ownerToken) {
    throw new Error("Only the person who published this listing can close it.");
  }

  const response = await fetch(`/api/listings/${listingId}/close`, {
    method: "POST",
    headers: {
      "X-Owner-Token": ownerToken
    }
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Could not close listing.");
  }

  listings = listings.map((listing) =>
    listing.id === data.id ? data : listing
  );
  renderListings();
  setListingsMessage("Listing moved to closed jobs.", "is-success");
  return data;
};

const renderListingSection = (grid, visibleListings, options) => {
  grid.innerHTML = "";

  if (!visibleListings.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state fade-in";
    empty.textContent = options.emptyMessage;
    grid.append(empty);
    return;
  }

  visibleListings.forEach((listing) => {
    const fragment = template.content.cloneNode(true);
    const card = fragment.querySelector(".listing-card");
    const status = fragment.querySelector(".listing-status");
    const closedMeta = fragment.querySelector(".listing-closed-meta");
    const closedAt = fragment.querySelector(".listing-closed-at");
    const closeButton = fragment.querySelector(".listing-close-button");

    fragment.querySelector(".listing-category").textContent = listing.category;
    fragment.querySelector(".listing-title").textContent = listing.title;
    status.textContent = options.isClosed ? "Closed" : listing.status;
    fragment.querySelector(".listing-pay").textContent = formatPay(listing);
    fragment.querySelector(".listing-description").textContent = listing.description;
    fragment.querySelector(".listing-location").textContent = listing.location;
    fragment.querySelector(".listing-deadline").textContent = formatDate(listing.deadline);
    fragment.querySelector(".listing-contact").textContent = listing.contact;
    card.classList.add("fade-in");
    card.dataset.listingId = listing.id;

    if (options.isClosed) {
      card.classList.add("is-closed");
      status.classList.add("is-closed");
      closedMeta.hidden = false;
      closedAt.textContent = formatClosedDate(listing.closed_at);
      closeButton.remove();
    } else if (ownsListing(listing)) {
      closeButton.dataset.listingId = listing.id;
    } else {
      closeButton.remove();
    }

    if (!options.isClosed) {
      card.classList.add("listing-card-selectable");
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `View details for ${listing.title}`);

    }

    grid.append(fragment);
  });
};

const renderListings = () => {
  const visibleListings = getFilteredListings();
  const activeListings = sortByTimestamp(
    visibleListings.filter((listing) => !listing.closed_at),
    "posted_at"
  );
  const closedListings = sortByTimestamp(
    visibleListings.filter((listing) => Boolean(listing.closed_at)),
    "closed_at"
  );

  renderListingSection(activeGrid, activeListings, {
    emptyMessage: "No active listings match that search yet. Try another category or post a new job.",
    isClosed: false
  });

  renderListingSection(closedGrid, closedListings, {
    emptyMessage: "No closed listings match that search yet.",
    isClosed: true
  });

  renderJobView();
};

const setMinimumDate = () => {
  const today = getTodayString();
  const deadlineInput = document.querySelector("#deadline");
  deadlineInput.min = today;
  deadlineInput.value = today;
};

const renderLoadingState = () => {
  activeGrid.innerHTML = "";
  closedGrid.innerHTML = "";

  const loading = document.createElement("div");
  loading.className = "empty-state fade-in";
  loading.textContent = "Loading listings from the server...";
  activeGrid.append(loading);
};

const loadListings = async () => {
  renderLoadingState();
  setListingsMessage("");

  try {
    const response = await fetch("/api/listings");
    if (!response.ok) {
      throw new Error("The server could not load listings.");
    }

    listings = await response.json();
    renderListings();
  } catch (error) {
    activeGrid.innerHTML = "";
    closedGrid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "empty-state fade-in";
    empty.textContent =
      "Could not load listings from the Python server. Start the app and refresh the page.";
    activeGrid.append(empty);
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const payload = {
    title: formData.get("title").toString().trim(),
    pay: Number(formData.get("pay")),
    pay_type: formData.get("pay_type").toString(),
    category: formData.get("category").toString(),
    location: formData.get("location").toString().trim(),
    deadline: formData.get("deadline").toString(),
    description: formData.get("description").toString().trim(),
    contact: formData.get("contact").toString().trim(),
    email: formData.get("email").toString().trim(),
    phone: formData.get("phone").toString().trim(),
    status: formData.get("status").toString()
  };

  submitButton.disabled = true;
  setMessage("Publishing listing...", "");

  try {
    const response = await fetch("/api/listings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not publish listing.");
    }

    ownerTokens[data.listing.id] = data.owner_token;
    saveOwnerTokens();
    listings = [data.listing, ...listings];
    renderListings();
    form.reset();
    setMinimumDate();
    form.querySelector("#title").focus();
    setMessage("Listing published successfully.", "is-success");
    setListingsMessage("");
  } catch (error) {
    setMessage(error.message, "is-error");
  } finally {
    submitButton.disabled = false;
  }
});

activeGrid.addEventListener("click", async (event) => {
  const button = event.target.closest(".listing-close-button");
  if (button) {
    button.disabled = true;
    setListingsMessage("Moving listing to closed jobs...", "");

    try {
      await closeListingById(button.dataset.listingId);
    } catch (error) {
      button.disabled = false;
      setListingsMessage(error.message, "is-error");
    }

    return;
  }

  const card = event.target.closest(".listing-card-selectable");
  if (card) {
    activeJobId = card.dataset.listingId;
    renderJobView();
  }
});

activeGrid.addEventListener("keydown", (event) => {
  const card = event.target.closest(".listing-card-selectable");
  if (!card || (event.key !== "Enter" && event.key !== " ")) {
    return;
  }

  event.preventDefault();
  activeJobId = card.dataset.listingId;
  renderJobView();
});

jobViewClose.addEventListener("click", closeJobView);

jobMessageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const listing = getListingById(activeJobId);
  const senderName = jobMessageSenderName.value.trim();
  const senderEmail = jobMessageSenderEmail.value.trim();
  const senderContact = jobMessageSenderContact.value.trim();
  const message = jobMessageBody.value.trim();

  if (!listing) {
    setJobMessageStatus("Open a job before sending a message.", "is-error");
    return;
  }

  if (!message) {
    setJobMessageStatus("Write a message first.", "is-error");
    return;
  }

  if (!senderName || !senderEmail || !senderContact) {
    setJobMessageStatus("Add your name, email, and contact before sending.", "is-error");
    return;
  }

  setJobMessageStatus("Sending message...", "");

  try {
    const response = await fetch("/api/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        listing_id: listing.id,
        sender_name: senderName,
        sender_email: senderEmail,
        sender_contact: senderContact,
        message
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not send message.");
    }

    setJobMessageStatus("Message sent to the seller by email and text.", "is-success");
    jobMessageBody.value = "";
  } catch (error) {
    setJobMessageStatus(error.message, "is-error");
  }
});

searchInput.addEventListener("input", renderListings);
categoryFilter.addEventListener("change", renderListings);

renderOpenTabs();
setMinimumDate();
loadListings();
