// Configuration
const CONFIG = {
  API_TOKEN: PropertiesService.getScriptProperties().getProperty("API_TOKEN"),
  BASE_URL:
    PropertiesService.getScriptProperties().getProperty("BASE_URL") ||
    "https://nepal-gms-chatbot.facets-ai.com/accessible-api",
};

// Function to request OAuth scopes (run this first to get permissions)
function requestOAuthScopes() {
  try {
    // This will trigger the OAuth permission request for external requests
    // Using a simple GET request to trigger the scope request
    const response = UrlFetchApp.fetch("https://httpbin.org/get", {
      method: "GET",
      headers: {
        "User-Agent": "GoogleAppsScript",
      },
    });

    Logger.log("OAuth scopes requested successfully");
    Logger.log("Response code:", response.getResponseCode());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "OAuth permissions granted! You can now use the external API.",
      "Success"
    );
  } catch (error) {
    Logger.log("OAuth scope request: " + error.toString());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "OAuth permission request failed. Please try again.",
      "Error"
    );
  }
}

// Function to test permissions
function testPermissions() {
  try {
    const response = UrlFetchApp.fetch("https://httpbin.org/get");
    Logger.log("Permission test: SUCCESS");
    Logger.log("Response code:", response.getResponseCode());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "External API permissions are working!",
      "Success"
    );
    return true;
  } catch (error) {
    Logger.log("Permission test: FAILED");
    Logger.log("Error:", error.toString());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "External API permissions failed. Run 'Request OAuth Scopes' first.",
      "Error"
    );
    return false;
  }
}

// Function to debug configuration
function debugConfiguration() {
  const scriptProperties = PropertiesService.getScriptProperties();
  const apiToken = scriptProperties.getProperty("API_TOKEN");
  const baseUrl = scriptProperties.getProperty("BASE_URL");

  Logger.log("=== Configuration Debug ===");
  Logger.log("API Token exists:", !!apiToken);
  Logger.log("API Token value:", apiToken ? "SET" : "NOT SET");
  Logger.log("Base URL:", baseUrl);
  Logger.log("Base URL value:", baseUrl ? "SET" : "NOT SET");
  Logger.log("OAuth Token available:", !!ScriptApp.getOAuthToken());

  // Test the CONFIG object
  Logger.log("CONFIG.BASE_URL:", CONFIG.BASE_URL);
  Logger.log("CONFIG.API_TOKEN:", CONFIG.API_TOKEN ? "SET" : "NOT SET");

  // Test the API endpoint
  try {
    const testResponse = UrlFetchApp.fetch("https://httpbin.org/get");
    Logger.log("External fetch test: SUCCESS");
  } catch (error) {
    Logger.log("External fetch test: FAILED - " + error.toString());
  }
}

// Function to create the appsscript.json manifest with correct OAuth scopes
function createManifest() {
  const manifest = {
    timeZone: "America/New_York",
    dependencies: {
      enabledAdvancedServices: [],
    },
    exceptionLogging: "STACKDRIVER",
    runtimeVersion: "V8",
    oauthScopes: [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/script.external_request",
    ],
  };

  Logger.log("=== Appsscript.json Manifest ===");
  Logger.log(JSON.stringify(manifest, null, 2));
  Logger.log(
    "Copy this to your appsscript.json file in the Apps Script editor"
  );

  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Manifest created! Check the logs for the appsscript.json content.",
    "Success"
  );
}

// Function to fetch and populate data
function fetchAndPopulateData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Clear existing data except header
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, 12).clear();
  }

  // Get the current configuration dynamically
  const scriptProperties = PropertiesService.getScriptProperties();
  const baseUrl = scriptProperties.getProperty("BASE_URL");
  const apiToken = scriptProperties.getProperty("API_TOKEN");

  if (!baseUrl || !apiToken) {
    Logger.log("[DEBUG] Missing configuration - Base URL or API Token not set");
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "❌ Configuration missing. Run 'Set Config Manually' first.",
      "Error"
    );
    return;
  }

  const options = {
    method: "GET",
    headers: {
      Authorization: `Bearer ${apiToken}`,
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    muteHttpExceptions: true, // This will prevent the script from failing on HTTP errors
  };

  try {
    Logger.log(`[DEBUG] Fetching data from: ${baseUrl}/gsheet-get-grievances`);
    const response = UrlFetchApp.fetch(
      `${baseUrl}/gsheet-get-grievances`,
      options
    );
    const responseCode = response.getResponseCode();
    const rawResponse = response.getContentText();
    Logger.log("[DEBUG] Response code: " + responseCode);
    Logger.log("[DEBUG] Raw response: " + rawResponse);

    if (responseCode === 200) {
      const data = JSON.parse(rawResponse);
      Logger.log(
        "[DEBUG] Parsed data structure:",
        JSON.stringify(data, null, 2)
      );

      if (data.data && data.data.data && data.data.data.length > 0) {
        // Prepare data for sheet
        const values = data.data.data.map((grievance) => [
          grievance.complainant_id,
          grievance.grievance_id,
          grievance.complainant_full_name,
          grievance.complainant_phone,
          grievance.complainant_municipality,
          grievance.complainant_village,
          grievance.complainant_address,
          grievance.grievance_description,
          grievance.grievance_summary,
          grievance.grievance_categories,
          grievance.grievance_creation_date,
          grievance.status || "SUBMITTED", // Default to SUBMITTED if status is null/empty
        ]);

        Logger.log(`[DEBUG] Prepared ${values.length} rows of data`);
        Logger.log(`[DEBUG] First row: ${JSON.stringify(values[0])}`);
        Logger.log(`[DEBUG] Second row: ${JSON.stringify(values[1])}`);

        // Clear existing data (except headers) before writing new data
        const lastRow = sheet.getLastRow();
        if (lastRow > 1) {
          Logger.log(
            `[DEBUG] Clearing existing data from rows 2 to ${lastRow}`
          );
          // Clear data and validation from the range
          const clearRange = sheet.getRange(2, 1, lastRow - 1, 12);
          clearRange.clear();
          clearRange.clearDataValidations();
        }

        // Check status values to see what we're trying to write
        const statusValues = values.map((row) => row[11]); // Status is column 12 (index 11)
        Logger.log(
          `[DEBUG] Status values being written: ${JSON.stringify(
            statusValues.slice(0, 5)
          )}`
        );

        // Write data to sheet starting from row 2 (after header)
        Logger.log(
          `[DEBUG] Writing ${values.length} rows to sheet starting at row 2`
        );

        try {
          sheet.getRange(2, 1, values.length, 12).setValues(values);
          Logger.log(
            `[DEBUG] Successfully wrote ${values.length} rows to sheet`
          );
        } catch (error) {
          Logger.log(`[DEBUG] Error writing to sheet: ${error.toString()}`);
          throw error;
        }

        // Show success message
        SpreadsheetApp.getActiveSpreadsheet().toast(
          `Data refreshed successfully! ${values.length} grievances loaded.`,
          "Success"
        );
        Logger.log(
          `[DEBUG] Successfully loaded ${values.length} grievances into the sheet`
        );
      } else {
        Logger.log("[DEBUG] No data found in response structure");
        Logger.log("[DEBUG] Data structure:", data);
        SpreadsheetApp.getActiveSpreadsheet().toast(
          "No data available in the response",
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
    "Setup Configuration",
    "Please enter your API token:",
    ui.ButtonSet.OK_CANCEL
  );

  if (tokenResponse.getSelectedButton() == ui.Button.OK) {
    const token = tokenResponse.getResponseText();
    PropertiesService.getScriptProperties().setProperty("API_TOKEN", token);
  }

  // Prompt for base URL with default value
  const urlResponse = ui.prompt(
    "Setup Configuration",
    "Please enter your API base URL (default: https://nepal-gms-chatbot.facets-ai.com/accessible-api):",
    ui.ButtonSet.OK_CANCEL
  );

  if (urlResponse.getSelectedButton() == ui.Button.OK) {
    const url =
      urlResponse.getResponseText() ||
      "https://nepal-gms-chatbot.facets-ai.com/accessible-api";
    PropertiesService.getScriptProperties().setProperty("BASE_URL", url);
  }

  ui.alert("Configuration saved successfully!");
}

// Function to set up the sheet
function setupSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Set up headers
  const headers = [
    "User ID",
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
    .createMenu("Nepal Chatbot")
    .addItem("Refresh Data", "fetchAndPopulateData")
    .addItem("Setup Configuration", "setupConfig")
    .addItem("Set Config Manually", "setConfigManually")
    .addItem("Test Connection", "testConnection")
    .addSeparator()
    .addItem("Clear Sheet & Start Fresh", "clearSheetAndStartFresh")
    .addItem("Disable All Data Validation", "disableAllDataValidation")
    .addItem("Setup Data Validation", "setupDataValidation")
    .addItem("Request Permissions", "requestOAuthScopes")
    .addItem("Force Permission Request", "forcePermissionRequest")
    .addItem("Test External Request", "testExternalRequest")
    .addItem("Update Manifest", "updateManifest")
    .addSeparator()
    .addItem("Check Current Office", "checkCurrentOffice")
    .addItem("Test onEdit Trigger", "testOnEditTrigger")
    .addItem("Debug Configuration", "debugConfiguration")
    .addToUi();
}

// Function to test connection to the API
function testConnection() {
  try {
    // Get the current configuration dynamically
    const scriptProperties = PropertiesService.getScriptProperties();
    const baseUrl = scriptProperties.getProperty("BASE_URL");

    if (!baseUrl) {
      Logger.log("[DEBUG] No BASE_URL configured");
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "❌ No Base URL configured. Run 'Set Config Manually' first.",
        "Error"
      );
      return false;
    }

    Logger.log(`[DEBUG] Testing connection to: ${baseUrl}/health`);

    const response = UrlFetchApp.fetch(`${baseUrl}/health`, {
      method: "GET",
      headers: {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "GoogleAppsScript",
      },
      muteHttpExceptions: true,
    });

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();

    Logger.log(
      `[DEBUG] Health check - Code: ${responseCode}, Response: ${responseText}`
    );

    if (responseCode === 200 && responseText.trim() === "OK") {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "✅ Connection successful! API is responding.",
        "Success"
      );
      return true;
    } else {
      Logger.log(
        `[DEBUG] Unexpected response - Code: ${responseCode}, Text: ${responseText}`
      );
      SpreadsheetApp.getActiveSpreadsheet().toast(
        `❌ Connection failed. Code: ${responseCode}, Response: ${responseText.substring(
          0,
          100
        )}...`,
        "Error"
      );
      return false;
    }
  } catch (error) {
    Logger.log(`[DEBUG] Connection test error: ${error.toString()}`);
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `❌ Connection error: ${error.toString()}`,
      "Error"
    );
    return false;
  }
}

// Function to force permission request
function forcePermissionRequest() {
  try {
    // Try multiple external requests to trigger permission dialog
    UrlFetchApp.fetch("https://httpbin.org/get");
    UrlFetchApp.fetch("https://httpbin.org/post", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify({ test: "data" }),
    });

    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Permission request triggered. Check for authorization dialog.",
      "Info"
    );
  } catch (error) {
    Logger.log("Force permission request: " + error.toString());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Permission request failed. Please try again.",
      "Error"
    );
  }
}

// Function to test external request
function testExternalRequest() {
  try {
    const response = UrlFetchApp.fetch("https://httpbin.org/get", {
      headers: {
        "User-Agent": "GoogleAppsScript",
      },
    });

    Logger.log("External request test: SUCCESS");
    Logger.log("Response code:", response.getResponseCode());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "External request test successful!",
      "Success"
    );
    return true;
  } catch (error) {
    Logger.log("External request test: FAILED");
    Logger.log("Error:", error.toString());
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "External request test failed. Check permissions.",
      "Error"
    );
    return false;
  }
}

// Function to update manifest
function updateManifest() {
  createManifest();
}

// Function to check current office
function checkCurrentOffice() {
  const selectedOffice =
    PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");
  const apiToken =
    PropertiesService.getScriptProperties().getProperty("API_TOKEN");

  Logger.log("=== Current Office Check ===");
  Logger.log("Selected Office:", selectedOffice);
  Logger.log("API Token exists:", !!apiToken);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Current Office: ${selectedOffice || "Not set"}`,
    "Info"
  );
}

// Function to test onEdit trigger
function testOnEditTrigger() {
  Logger.log("onEdit trigger test executed");
  SpreadsheetApp.getActiveSpreadsheet().toast(
    "onEdit trigger test successful!",
    "Success"
  );
}

// Function to manually set configuration (for testing)
function setConfigManually() {
  const scriptProperties = PropertiesService.getScriptProperties();

  // Set the configuration manually
  scriptProperties.setProperty(
    "API_TOKEN",
    "chatbot_gsheet_y2eSsukkKRLfQ34x6hk2D0E2"
  );
  scriptProperties.setProperty(
    "BASE_URL",
    "https://octavio-nonfigurative-unsinfully.ngrok-free.dev"
  );

  Logger.log("Configuration set manually:");
  Logger.log("API_TOKEN:", scriptProperties.getProperty("API_TOKEN"));
  Logger.log("BASE_URL:", scriptProperties.getProperty("BASE_URL"));

  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Configuration set manually! Run debugConfiguration to verify.",
    "Success"
  );
}

// Function to clear the entire sheet and start fresh
function clearSheetAndStartFresh() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  try {
    // Clear all data and formatting
    sheet.clear();

    // Clear all data validation
    const allRange = sheet.getDataRange();
    allRange.clearDataValidations();

    Logger.log(
      "[DEBUG] Cleared entire sheet - data, formatting, and validation"
    );
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Sheet cleared completely. Run 'Refresh Data' to populate with fresh data.",
      "Success"
    );
  } catch (error) {
    Logger.log(`[DEBUG] Error clearing sheet: ${error.toString()}`);
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Error clearing sheet: ${error.toString()}`,
      "Error"
    );
  }
}

// Function to completely disable all data validation
function disableAllDataValidation() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  try {
    // Get the entire sheet range
    const maxRows = sheet.getMaxRows();
    const maxCols = sheet.getMaxColumns();
    const allRange = sheet.getRange(1, 1, maxRows, maxCols);

    // Clear all data validation from the entire sheet
    allRange.clearDataValidations();

    Logger.log("[DEBUG] Disabled all data validation from the entire sheet");
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "All data validation disabled. You can now write any data without validation errors.",
      "Success"
    );
  } catch (error) {
    Logger.log(`[DEBUG] Error disabling data validation: ${error.toString()}`);
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Error disabling data validation: ${error.toString()}`,
      "Error"
    );
  }
}

// Function to set up proper data validation for the Status column
function setupDataValidation() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  try {
    // First, clear all existing data validation from the sheet
    Logger.log("[DEBUG] Clearing all existing data validation...");
    const allRange = sheet.getDataRange();
    allRange.clearDataValidations();

    // Define valid status values from the API
    const validStatuses = [
      "SUBMITTED",
      "UNDER_EVALUATION",
      "ESCALATED",
      "RESOLVED",
      "DENIED",
      "DISPUTED",
      "CLOSED",
    ];

    // Set up data validation for the Status column (column L, index 12)
    const statusColumn = 12; // Column L
    const lastRow = sheet.getLastRow();

    if (lastRow > 1) {
      const statusRange = sheet.getRange(2, statusColumn, lastRow - 1, 1);

      // Create data validation rule
      const rule = SpreadsheetApp.newDataValidation()
        .requireValueInList(validStatuses, true) // true allows blank values
        .setAllowInvalid(false)
        .setHelpText("Select a valid grievance status")
        .build();

      statusRange.setDataValidation(rule);

      Logger.log(
        `[DEBUG] Set up data validation for Status column with values: ${validStatuses.join(
          ", "
        )}`
      );
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "Data validation set up for Status column",
        "Success"
      );
    } else {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "No data rows found. Add some data first.",
        "Info"
      );
    }
  } catch (error) {
    Logger.log(`[DEBUG] Error setting up data validation: ${error.toString()}`);
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Error setting up data validation: ${error.toString()}`,
      "Error"
    );
  }
}

// Function to run on sheet open
function onOpen() {
  setupSheet();
  // Check if configuration exists
  if (!PropertiesService.getScriptProperties().getProperty("API_TOKEN")) {
    setupConfig();
  }
  fetchAndPopulateData();
}

// Function to refresh data periodically (can be set up as a trigger)
function refreshData() {
  fetchAndPopulateData();
}

function testDataRefresh() {
  try {
    fetchAndPopulateData();
    Logger.log("Refresh completed - check the sheet for data");
  } catch (error) {
    Logger.log("Error during refresh: " + error.toString());
  }
}

function checkProperties() {
  const scriptProperties = PropertiesService.getScriptProperties();
  const apiToken = scriptProperties.getProperty("API_TOKEN");
  const baseUrl = scriptProperties.getProperty("BASE_URL");

  Logger.log("API Token:", apiToken);
  Logger.log("Base URL:", baseUrl);
}
