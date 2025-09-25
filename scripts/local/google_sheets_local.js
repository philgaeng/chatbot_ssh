// Local Development Google Sheets Script for Nepal Chatbot Monitoring
// This script is configured to work with your local WSL development environment

// Configuration for local development
const CONFIG = {
  API_TOKEN: PropertiesService.getScriptProperties().getProperty("API_TOKEN"),
  BASE_URL:
    PropertiesService.getScriptProperties().getProperty("BASE_URL") ||
    "https://your-ngrok-url.ngrok.io",
};

// Function to fetch and populate data
function fetchAndPopulateData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Clear existing data except header
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, 12).clear();
  }

  const options = {
    method: "GET",
    headers: {
      Authorization: `Bearer ${CONFIG.API_TOKEN}`,
      "Content-Type": "application/json",
    },
    muteHttpExceptions: true, // This will prevent the script from failing on HTTP errors
  };

  try {
    const response = UrlFetchApp.fetch(
      `${CONFIG.BASE_URL}/gsheet-get-grievances`,
      options
    );
    const responseCode = response.getResponseCode();
    const rawResponse = response.getContentText();
    Logger.log("[DEBUG] Response code: " + responseCode);
    Logger.log("[DEBUG] Raw response: " + rawResponse);

    if (responseCode === 200) {
      const data = JSON.parse(rawResponse);

      if (data.status === "success" && data.data.data.length > 0) {
        // Prepare data for sheet - Note: field mapping updated for your local API
        const values = data.data.data.map((grievance) => [
          grievance.complainant_id, // User ID
          grievance.grievance_id, // Grievance ID
          grievance.complainant_full_name, // Full Name
          grievance.complainant_phone, // Contact Phone
          grievance.complainant_municipality, // Municipality
          grievance.complainant_village, // Village
          grievance.complainant_address, // Address
          grievance.grievance_description, // Grievance Details
          grievance.grievance_summary, // Summary
          grievance.grievance_categories, // Categories
          grievance.grievance_creation_date, // Creation Date
          grievance.status, // Status
        ]);

        // Write data to sheet starting from row 2 (after header)
        sheet.getRange(2, 1, values.length, 12).setValues(values);

        // Show success message
        SpreadsheetApp.getActiveSpreadsheet().toast(
          "Data refreshed successfully!",
          "Success"
        );
      } else {
        SpreadsheetApp.getActiveSpreadsheet().toast(
          "No data available",
          "Info"
        );
      }
    } else {
      Logger.log("[DEBUG] Error response: " + rawResponse);
      const errorData = JSON.parse(rawResponse);
      SpreadsheetApp.getActiveSpreadsheet().toast(
        `Error: ${errorData.message || "Failed to fetch data"}`,
        "Error"
      );
    }
  } catch (err) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Error: ${err.message}`,
      "Error"
    );
    Logger.log("[DEBUG] Error fetching data: " + err.message);
  }
}

// Function to set up configuration
function setupConfig() {
  const ui = SpreadsheetApp.getUi();

  // Prompt for API token
  const tokenResponse = ui.prompt(
    "Setup Configuration - Local Development",
    "Please enter your local API token (same as GSHEET_BEARER_TOKEN in env.local):",
    ui.ButtonSet.OK_CANCEL
  );

  if (tokenResponse.getSelectedButton() == ui.Button.OK) {
    const token = tokenResponse.getResponseText();
    PropertiesService.getScriptProperties().setProperty("API_TOKEN", token);
  }

  // Prompt for base URL with default value
  const urlResponse = ui.prompt(
    "Setup Configuration - Local Development",
    "Please enter your ngrok URL (e.g., https://abc123.ngrok.io):",
    ui.ButtonSet.OK_CANCEL
  );

  if (urlResponse.getSelectedButton() == ui.Button.OK) {
    const url = urlResponse.getResponseText();
    PropertiesService.getScriptProperties().setProperty("BASE_URL", url);
  }

  ui.alert("Configuration saved successfully!");
}

// Function to set up the sheet
function setupSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Set up headers
  const headers = [
    "Complainant ID",
    "Grievance ID",
    "Full Name",
    "Contact Phone",
    "Municipality",
    "Village",
    "Address",
    "Grievance Details",
    "Summary",
    "Categories",
    "Creation Date",
    "Status",
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");

  // Add menu items
  SpreadsheetApp.getUi()
    .createMenu("Nepal Chatbot - Local Dev")
    .addItem("Refresh Data", "fetchAndPopulateData")
    .addItem("Setup Configuration", "setupConfig")
    .addItem("Test Connection", "testConnection")
    .addToUi();
}

// Function to test the connection
function testConnection() {
  const ui = SpreadsheetApp.getUi();

  try {
    const response = UrlFetchApp.fetch(`${CONFIG.BASE_URL}/health`, {
      method: "GET",
      muteHttpExceptions: true,
    });

    const responseCode = response.getResponseCode();

    if (responseCode === 200) {
      ui.alert(
        "Connection Test",
        "✅ Successfully connected to local API!",
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        "Connection Test",
        `❌ Connection failed. Response code: ${responseCode}`,
        ui.ButtonSet.OK
      );
    }
  } catch (error) {
    ui.alert(
      "Connection Test",
      `❌ Connection failed: ${error.message}`,
      ui.ButtonSet.OK
    );
  }
}

// Function to run on sheet open
function onOpen() {
  setupSheet();

  // Check if configuration exists
  const apiToken =
    PropertiesService.getScriptProperties().getProperty("API_TOKEN");
  const baseUrl =
    PropertiesService.getScriptProperties().getProperty("BASE_URL");

  if (!apiToken || !baseUrl || baseUrl.includes("your-ngrok-url")) {
    const ui = SpreadsheetApp.getUi();
    const result = ui.alert(
      "Setup Required",
      "Please configure your local API settings first.",
      ui.ButtonSet.OK_CANCEL
    );

    if (result == ui.Button.OK) {
      setupConfig();
    }
  } else {
    // Auto-refresh data on open if configured
    fetchAndPopulateData();
  }
}

// Function to refresh data periodically (can be set up as a trigger)
function refreshData() {
  fetchAndPopulateData();
}

// Function for manual testing
function testDataRefresh() {
  try {
    fetchAndPopulateData();
    Logger.log("Refresh completed - check the sheet for data");
  } catch (error) {
    Logger.log("Error during refresh: " + error.toString());
  }
}

// Function to check current configuration
function checkProperties() {
  const scriptProperties = PropertiesService.getScriptProperties();
  const apiToken = scriptProperties.getProperty("API_TOKEN");
  const baseUrl = scriptProperties.getProperty("BASE_URL");

  Logger.log("API Token:", apiToken ? "Set" : "Not set");
  Logger.log("Base URL:", baseUrl);

  const ui = SpreadsheetApp.getUi();
  ui.alert(
    "Current Configuration",
    `Base URL: ${baseUrl}\nAPI Token: ${apiToken ? "Set" : "Not set"}`,
    ui.ButtonSet.OK
  );
}
