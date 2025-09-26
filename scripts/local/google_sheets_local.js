// Local Development Google Sheets Script for Nepal Chatbot Monitoring
// This script is configured to work with your local WSL development environment

// Required permissions for external API calls
// This script requires the following OAuth scopes:
// - https://www.googleapis.com/auth/script.external_request
// - https://www.googleapis.com/auth/spreadsheets

// Configuration for local development
const CONFIG = {
  API_TOKEN: PropertiesService.getScriptProperties().getProperty("API_TOKEN"),
  BASE_URL:
    PropertiesService.getScriptProperties().getProperty("BASE_URL") ||
    "https://your-ngrok-url.ngrok.io",
  // Default credentials for testing
  DEFAULT_USERNAME:
    PropertiesService.getScriptProperties().getProperty("DEFAULT_USERNAME") ||
    "pd_office",
  DEFAULT_PASSWORD:
    PropertiesService.getScriptProperties().getProperty("DEFAULT_PASSWORD") ||
    "1234",
};

// Function to get authentication parameters from sheet
function getAuthenticationParams() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Try to get username and password from named ranges or specific cells
  let username = CONFIG.DEFAULT_USERNAME;
  let password = CONFIG.DEFAULT_PASSWORD;

  try {
    // Check if there are named ranges for authentication
    const usernameRange =
      SpreadsheetApp.getActiveSpreadsheet().getRangeByName("USERNAME");
    const passwordRange =
      SpreadsheetApp.getActiveSpreadsheet().getRangeByName("PASSWORD");

    if (usernameRange) {
      username = usernameRange.getValue();
    }
    if (passwordRange) {
      password = passwordRange.getValue();
    }
  } catch (e) {
    Logger.log("[DEBUG] No named ranges found, using default credentials");
  }

  Logger.log(`[DEBUG] Using authentication: username=${username}`);
  return { username, password };
}

// Function to clear all data except headers
function clearAllData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Clear all data except the header row
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, SHEET_COLUMNS).clear();
  }

  // Add security notice back
  const headers = [
    "Complainant ID",
    "Grievance ID",
    "Status",
    "Timeline",
    "Full Name",
    "Contact Phone",
    "Municipality",
    "Village",
    "Address",
    "Grievance Details",
    "Summary",
    "Categories",
    "Sensitive Issue",
    "High Priority",
    "Creation Date",
    "Status Update Date",
    "Notes",
  ];

  // Create security notice array that matches headers length
  const securityNotice = [
    "🔒 Authentication Required",
    "Please use the menu to authenticate",
    "and access your office's data",
  ];

  // Fill the rest with empty strings to match headers.length
  while (securityNotice.length < headers.length) {
    securityNotice.push("");
  }

  sheet.getRange(2, 1, 1, headers.length).setValues([securityNotice]);
  sheet.getRange(2, 1, 1, headers.length).setBackground("#fff3cd");
  sheet.getRange(2, 1, 1, headers.length).setFontStyle("italic");

  // Clear any selected office and temp office to force re-authentication
  PropertiesService.getScriptProperties().deleteProperty("SELECTED_OFFICE");
  PropertiesService.getScriptProperties().deleteProperty("TEMP_OFFICE");

  Logger.log("[DEBUG] Sheet cleared - authentication required");
}

// Function to show office selection dialog using native UI
function showOfficeSelectionDialog() {
  const ui = SpreadsheetApp.getUi();

  // Create a simple text-based selection
  const officeOptions = [
    "1. PD Office (Admin) - View all grievances",
    "2. ADB Headquarters (Admin) - View all grievances",
    "3. Office 1 - Birtamod - View grievances from Birtamod & Charaali",
    "4. Office 2 - Mechinagar - View grievances from Mechinagar",
    "5. Office 3 - Dhulabari - View grievances from Dhulabari & Butabari",
    "6. Office 4 - Dhaijan - View grievances from Dhaijan",
    "7. Office 5 - Kankai - View grievances from Kankai",
  ];

  const officeMapping = {
    1: "pd_office",
    2: "Adb_hq",
    3: "Office_1",
    4: "Office_2",
    5: "Office_3",
    6: "Office_4",
    7: "Office_5",
  };

  const response = ui.prompt(
    "🏢 Office Authentication",
    `Please select your office by entering the number (1-7):\n\n${officeOptions.join(
      "\n"
    )}\n\nEnter your choice:`,
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() == ui.Button.OK) {
    const choice = response.getResponseText().trim();

    if (officeMapping[choice]) {
      const officeId = officeMapping[choice];
      Logger.log(`[DEBUG] User selected office: ${officeId}`);

      // Store the selected office temporarily
      PropertiesService.getScriptProperties().setProperty(
        "TEMP_OFFICE",
        officeId
      );

      // Show password prompt
      showPasswordDialog(officeId);
    } else {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "❌ Invalid selection. Please try again.",
        "Error"
      );
      showOfficeSelectionDialog();
    }
  } else {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Authentication cancelled",
      "Info"
    );
  }
}

// Function to handle office selection and refresh data
function selectOfficeAndRefresh(officeId) {
  if (officeId === "cancel") {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Authentication cancelled",
      "Info"
    );
    return;
  }

  // Store the selected office temporarily
  PropertiesService.getScriptProperties().setProperty("TEMP_OFFICE", officeId);

  // Show password prompt
  showPasswordDialog(officeId);
}

// Function to show password dialog
function showPasswordDialog(officeId) {
  const ui = SpreadsheetApp.getUi();

  // Get office name for display
  const offices = {
    pd_office: "PD Office (Admin)",
    Adb_hq: "ADB Headquarters (Admin)",
    Office_1: "Office 1 - Birtamod",
    Office_2: "Office 2 - Mechinagar",
    Office_3: "Office 3 - Dhulabari",
    Office_4: "Office 4 - Dhaijan",
    Office_5: "Office 5 - Kankai",
  };

  const officeName = offices[officeId] || officeId;

  const response = ui.prompt(
    "🔐 Password Authentication",
    `Please enter the password for ${officeName}:\n\nEnter password:`,
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() == ui.Button.OK) {
    const password = response.getResponseText();

    // Verify password (for now, all offices use "1234")
    if (password === "1234") {
      // Store the selected office as authenticated
      PropertiesService.getScriptProperties().setProperty(
        "SELECTED_OFFICE",
        officeId
      );
      PropertiesService.getScriptProperties().deleteProperty("TEMP_OFFICE");

      // Show confirmation
      SpreadsheetApp.getActiveSpreadsheet().toast(
        `✅ Authenticated as: ${officeName}`,
        "Authentication Success"
      );

      // Refresh data with the selected office
      Logger.log(`[DEBUG] Authenticated office: ${officeId}`);
      fetchAndPopulateDataWithOffice(officeId);
    } else {
      // Invalid password
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "❌ Invalid password. Please try again.",
        "Authentication Failed"
      );

      // Clear temp office and show authentication dialog again
      PropertiesService.getScriptProperties().deleteProperty("TEMP_OFFICE");
      showOfficeSelectionDialog();
    }
  } else {
    // User cancelled password entry
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Authentication cancelled",
      "Info"
    );

    // Clear temp office and show authentication dialog again
    PropertiesService.getScriptProperties().deleteProperty("TEMP_OFFICE");
    showOfficeSelectionDialog();
  }
}

// Function to fetch data with specific office
function fetchAndPopulateDataWithOffice(officeId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Clear existing data except header
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, SHEET_COLUMNS).clear();
  }

  const options = {
    method: "GET",
    headers: {
      Authorization: `Bearer ${officeId}`,
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    muteHttpExceptions: true,
  };

  try {
    const response = UrlFetchApp.fetch(
      `${CONFIG.BASE_URL}/gsheet-get-grievances`,
      options
    );
    const responseCode = response.getResponseCode();
    const rawResponse = response.getContentText();

    Logger.log(`[DEBUG] Office: ${officeId}, Response code: ${responseCode}`);

    if (responseCode === 200) {
      const data = JSON.parse(rawResponse);

      if (
        data.status === "SUCCESS" &&
        data.data.data &&
        data.data.data.length > 0
      ) {
        // Prepare data for sheet (matching header order)
        const values = data.data.data.map((grievance) => [
          grievance.complainant_id, // Column A: Complainant ID
          grievance.grievance_id, // Column B: Grievance ID
          grievance.status, // Column C: Status
          grievance.grievance_timeline, // Column D: Timeline
          grievance.complainant_full_name, // Column E: Full Name
          grievance.complainant_phone, // Column F: Contact Phone
          grievance.complainant_municipality, // Column G: Municipality
          grievance.complainant_village, // Column H: Village
          grievance.complainant_address, // Column I: Address
          grievance.grievance_description, // Column J: Grievance Details
          grievance.grievance_summary, // Column K: Summary
          grievance.grievance_categories, // Column L: Categories
          grievance.grievance_sensitive_issue, // Column M: Sensitive Issue
          grievance.grievance_high_priority, // Column N: High Priority
          grievance.grievance_creation_date, // Column O: Creation Date
          grievance.grievance_status_update_date, // Column P: Status Update Date
          grievance.notes, // Column Q: Notes
        ]);

        // Write data to sheet
        sheet.getRange(2, 1, values.length, SHEET_COLUMNS).setValues(values);

        // Update sheet protection for new data rows
        protectSheet();

        // Show success message with office info
        const offices = {
          pd_office: "PD Office (Admin)",
          adb_hq: "ADB Headquarters (Admin)",
          office_1: "Office 1 - Birtamod",
          office_2: "Office 2 - Mechinagar",
          office_3: "Office 3 - Dhulabari",
          office_4: "Office 4 - Dhaijan",
          office_5: "Office 5 - Kankai",
        };

        SpreadsheetApp.getActiveSpreadsheet().toast(
          `✅ Data refreshed! Showing ${values.length} grievances for ${
            offices[officeId] || officeId
          }`,
          "Success"
        );
      } else {
        SpreadsheetApp.getActiveSpreadsheet().toast(
          "No grievances found for your office",
          "Info"
        );
      }
    } else {
      Logger.log(`[DEBUG] Error response: ${rawResponse}`);
      const errorData = JSON.parse(rawResponse);
      SpreadsheetApp.getActiveSpreadsheet().toast(
        `❌ Error: ${errorData.message || "Failed to fetch data"}`,
        "Error"
      );
    }
  } catch (err) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `❌ Error: ${err.message}`,
      "Error"
    );
    Logger.log(`[DEBUG] Error fetching data: ${err.message}`);
  }
}

// Function to fetch and populate data
function fetchAndPopulateData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Clear existing data except header
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, SHEET_COLUMNS).clear();
  }

  // Check if office is selected, otherwise use default authentication
  const selectedOffice =
    PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");
  let username;

  if (selectedOffice) {
    username = selectedOffice;
    Logger.log(`[DEBUG] Using selected office: ${username}`);
  } else {
    // Fallback to old authentication method
    const auth = getAuthenticationParams();
    username = auth.username;
    Logger.log(`[DEBUG] Using fallback authentication: ${username}`);
  }

  const options = {
    method: "GET",
    headers: {
      Authorization: `Bearer ${username}`,
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true", // Skip ngrok warning page
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

      Logger.log(
        "[DEBUG] Response structure: status=" +
          data.status +
          ", data.count=" +
          data.data.count +
          ", data.data.length=" +
          data.data.data.length
      );

      if (
        data.status === "SUCCESS" &&
        data.data.data &&
        data.data.data.length > 0
      ) {
        // Prepare data for sheet - Note: field mapping updated for your local API
        const values = data.data.data.map((grievance) => [
          grievance.complainant_id, // User ID
          grievance.grievance_id, // Grievance ID
          grievance.status, // Status
          grievance.grievance_timeline, // Timeline
          grievance.complainant_full_name, // Full Name
          grievance.complainant_phone, // Contact Phone
          grievance.complainant_municipality, // Municipality
          grievance.complainant_village, // Village
          grievance.complainant_address, // Address
          grievance.grievance_description, // Grievance Details
          grievance.grievance_summary, // Summary
          grievance.grievance_categories, // Categories
          grievance.grievance_sensitive_issue, // Sensitive Issue
          grievance.grievance_high_priority, // High Priority
          grievance.grievance_creation_date, // Creation Date
          grievance.grievance_status_update_date, // Status Update Date
          grievance.notes, // Notes
        ]);

        Logger.log(
          "[DEBUG] Prepared " + values.length + " rows for writing to sheet"
        );
        Logger.log("[DEBUG] First row sample: " + JSON.stringify(values[0]));

        // Write data to sheet starting from row 2 (after header)
        sheet.getRange(2, 1, values.length, SHEET_COLUMNS).setValues(values);

        // Update sheet protection for new data rows
        protectSheet();

        // Show success message with office info
        const offices = {
          pd_office: "PD Office (Admin)",
          adb_hq: "ADB Headquarters (Admin)",
          office_1: "Office 1 - Birtamod",
          office_2: "Office 2 - Mechinagar",
          office_3: "Office 3 - Dhulabari",
          office_4: "Office 4 - Dhaijan",
          office_5: "Office 5 - Kankai",
        };

        const officeName = offices[username] || username;
        SpreadsheetApp.getActiveSpreadsheet().toast(
          `✅ Data refreshed! Showing ${values.length} grievances for ${officeName}`,
          "Success"
        );
      } else {
        Logger.log(
          "[DEBUG] No data condition - status: " +
            data.status +
            ", expected: SUCCESS, data.data exists: " +
            (data.data ? "yes" : "no") +
            ", data.data.data length: " +
            (data.data && data.data.data ? data.data.data.length : "undefined")
        );
        SpreadsheetApp.getActiveSpreadsheet().toast(
          "No data available - check logs for details",
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
// Constants for sheet configuration
const SHEET_COLUMNS = 17; // Total number of columns including headers

function setupSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Set up headers
  const headers = [
    "Complainant ID",
    "Grievance ID",
    "Status",
    "Timeline",
    "Full Name",
    "Contact Phone",
    "Municipality",
    "Village",
    "Address",
    "Grievance Details",
    "Summary",
    "Categories",
    "Sensitive Issue",
    "High Priority",
    "Creation Date",
    "Status Update Date",
    "Notes",
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");

  // Add a security notice in row 2
  const securityNotice = [
    "🔒 Authentication Required",
    "Please use the menu to authenticate",
    "and access your office's data",
  ];

  // Fill the rest with empty strings to match headers.length
  while (securityNotice.length < headers.length) {
    securityNotice.push("");
  }

  sheet.getRange(2, 1, 1, headers.length).setValues([securityNotice]);
  sheet.getRange(2, 1, 1, headers.length).setBackground("#fff3cd");
  sheet.getRange(2, 1, 1, headers.length).setFontStyle("italic");

  // Add menu items
  SpreadsheetApp.getUi()
    .createMenu("Nepal Chatbot - Local Dev")
    .addItem("🏢 Office Authentication", "showOfficeSelectionDialog")
    .addItem("🔒 Sign Out & Clear Data", "signOutAndClear")
    .addSeparator()
    .addItem("🔄 Refresh Data", "fetchAndPopulateData")
    .addItem("⚙️ Setup Configuration", "setupConfig")
    .addItem("🔍 Test Connection", "testConnection")
    .addItem("🔑 Request Permissions", "triggerPermissionRequest")
    .addItem("⚡ Force Permission Request", "forcePermissionRequest")
    .addItem("🌐 Test External Request", "testExternalRequestPermission")
    .addItem("📋 Update Manifest", "showManifestInstructions")
    .addSeparator()
    .addItem("🛡️ Update Sheet Protection", "protectSheet")
    .addItem("ℹ️ Check Current Office", "checkCurrentOffice")
    .addSeparator()
    .addItem("🧪 Test onEdit Trigger", "testOnEditTrigger")
    .addToUi();

  // Setup data validation for status column (Column C)
  setupStatusValidation();

  // Protect the sheet to allow only status column editing
  protectSheet();

  console.log("[SUCCESS] Sheet setup completed - menu should be visible");
}

// Manual test function to debug menu setup
function testMenuSetup() {
  console.log("[INFO] Testing menu setup...");
  setupSheet();
  console.log("[SUCCESS] Menu setup test completed");
}

// Debug function to test data fetching
function debugDataFetch() {
  const selectedOffice =
    PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");
  Logger.log(`Selected office: ${selectedOffice}`);

  if (!selectedOffice) {
    console.log("[WARNING] No office selected - please authenticate first");
    return;
  }

  console.log("[INFO] Fetching data...");
  fetchAndPopulateDataWithOffice(selectedOffice);
  console.log("[SUCCESS] Data fetch completed");
}

// Test function to simulate onEdit trigger
function testOnEditTrigger() {
  console.log("[INFO] Testing onEdit trigger manually...");

  // Get the active sheet and simulate an edit event
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const activeRange = sheet.getActiveRange();

  if (!activeRange) {
    console.log("[WARNING] No active range selected");
    return;
  }

  const row = activeRange.getRow();
  const col = activeRange.getColumn();
  const value = activeRange.getValue();

  Logger.log(
    `[DEBUG] Active range - Row: ${row}, Col: ${col}, Value: ${value}`
  );

  // Only test if it's the status column (Column C = 3)
  if (col === 3 && row > 1) {
    Logger.log(`[DEBUG] Testing status column edit in row ${row}`);

    // Simulate an edit event
    const mockEvent = {
      range: activeRange,
      value: value,
      oldValue: "SUBMITTED", // Mock old value
    };

    try {
      onEdit(mockEvent);
      console.log("[SUCCESS] onEdit trigger test completed");
    } catch (error) {
      console.log(`[WARNING] onEdit trigger test failed: ${error.message}`);
      Logger.log(`[ERROR] onEdit trigger test failed: ${error.message}`);
    }
  } else {
    console.log(
      "[INFO] Please select a cell in the Status column (Column C) to test"
    );
  }
}

// Simple function to request permissions
function requestPermissions() {
  const ui = SpreadsheetApp.getUi();

  try {
    // This will trigger the permission request dialog
    const response = UrlFetchApp.fetch("https://httpbin.org/get", {
      method: "GET",
      muteHttpExceptions: true,
    });

    ui.alert(
      "Permissions Granted!",
      "✅ External request permissions have been granted.\n\nYou can now use the status update feature.",
      ui.ButtonSet.OK
    );
  } catch (error) {
    ui.alert(
      "Permission Required",
      "❌ External request permissions are required.\n\nPlease run this function and grant permissions when prompted.\n\nError: " +
        error.message,
      ui.ButtonSet.OK
    );
  }
}

// Simple function to trigger permission request
function triggerPermissionRequest() {
  console.log("[INFO] Triggering permission request...");

  try {
    // Make a simple request to trigger permission dialog
    UrlFetchApp.fetch("https://www.google.com", {
      method: "GET",
      muteHttpExceptions: true,
    });

    console.log("[SUCCESS] Permission request triggered successfully");
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Permission request sent! Please grant permissions when prompted.",
      "Permission Request",
      5
    );
  } catch (error) {
    console.log(`[WARNING] Permission request failed: ${error.message}`);

    if (error.message.includes("permissions are not sufficient")) {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "Please grant external request permissions in Apps Script",
        "Permission Required",
        5
      );
    }
  }
}

// Function to test the connection and request permissions
function testConnection() {
  const ui = SpreadsheetApp.getUi();

  try {
    // First, try to make a simple request to trigger permission request
    const response = UrlFetchApp.fetch(`${CONFIG.BASE_URL}/health`, {
      method: "GET",
      headers: {
        "ngrok-skip-browser-warning": "true", // Skip ngrok warning page
      },
      muteHttpExceptions: true,
    });

    const responseCode = response.getResponseCode();

    if (responseCode === 200) {
      ui.alert(
        "Connection Test",
        "✅ Successfully connected to local API!\n\nPermissions are properly configured.",
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        "Connection Test",
        `❌ Connection failed. Response code: ${responseCode}\n\nPlease check your ngrok URL and API configuration.`,
        ui.ButtonSet.OK
      );
    }
  } catch (error) {
    if (error.message.includes("permissions are not sufficient")) {
      ui.alert(
        "⚠️ Permissions Required",
        `❌ External request permissions not granted.\n\nTo fix this:\n1. Go to Extensions → Apps Script\n2. Run this testConnection function\n3. Grant permissions when prompted\n4. Try again\n\nError: ${error.message}`,
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        "Connection Test",
        `❌ Connection failed: ${error.message}\n\nPlease check your ngrok URL and API configuration.`,
        ui.ButtonSet.OK
      );
    }
  }
}

// Function to run on sheet open
function onOpen() {
  console.log("onOpen triggered");
  setupSheet();

  // Check if configuration exists
  const apiToken =
    PropertiesService.getScriptProperties().getProperty("API_TOKEN");
  const baseUrl =
    PropertiesService.getScriptProperties().getProperty("BASE_URL");
  const selectedOffice =
    PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");
  const tempOffice =
    PropertiesService.getScriptProperties().getProperty("TEMP_OFFICE");

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
    // Clear any existing data to ensure blank state
    clearAllData();

    // Check if user was in the middle of authentication
    if (tempOffice) {
      // Continue with password authentication
      showPasswordDialog(tempOffice);
    } else if (selectedOffice) {
      // User is already authenticated, refresh data
      fetchAndPopulateDataWithOffice(selectedOffice);
    } else {
      // Show office selection dialog for new authentication
      showOfficeSelectionDialog();
    }
  }
}

// Force menu update function
function forceMenuUpdate() {
  console.log("[INFO] Forcing menu update...");
  setupSheet();
  console.log("[SUCCESS] Menu updated - please check the Nepal Chatbot menu");
  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Menu updated! Please check the Nepal Chatbot menu.",
    "Menu Update",
    3
  );
}

// Function to force permission request by creating a new trigger
function forcePermissionRequest() {
  console.log("[INFO] Forcing permission request...");

  try {
    // Delete existing triggers first
    const triggers = ScriptApp.getProjectTriggers();
    triggers.forEach((trigger) => {
      if (trigger.getHandlerFunction() === "onEdit") {
        ScriptApp.deleteTrigger(trigger);
      }
    });

    // Create a new onEdit trigger - this will prompt for permissions
    ScriptApp.newTrigger("onEdit")
      .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
      .onEdit()
      .create();

    console.log(
      "[SUCCESS] New onEdit trigger created - permissions should be requested"
    );
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "New trigger created! Please grant permissions when prompted.",
      "Permission Request",
      5
    );
  } catch (error) {
    console.log(`[WARNING] Failed to create trigger: ${error.message}`);
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Failed to create trigger. Please manually grant permissions.",
      "Error",
      5
    );
  }
}

// Function to refresh data periodically (can be set up as a trigger)
function refreshData() {
  fetchAndPopulateData();
}

// Test function specifically for external request permissions
function testExternalRequestPermission() {
  console.log("[INFO] Testing external request permission...");

  try {
    // This should trigger the permission request if not already granted
    const response = UrlFetchApp.fetch("https://httpbin.org/get", {
      method: "GET",
      muteHttpExceptions: true,
    });

    console.log(
      `[SUCCESS] External request works! Response code: ${response.getResponseCode()}`
    );
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "External request permission is working!",
      "Permission Test",
      3
    );

    return true;
  } catch (error) {
    console.log(`[WARNING] External request failed: ${error.message}`);

    if (error.message.includes("permissions are not sufficient")) {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        "External request permission required. Please grant permissions when prompted.",
        "Permission Required",
        5
      );
    }

    return false;
  }
}

// Function to show appsscript.json instructions
function showManifestInstructions() {
  const ui = SpreadsheetApp.getUi();

  const manifestContent = `{
  "timeZone": "Asia/Kathmandu",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}`;

  ui.alert(
    "Update appsscript.json",
    `Please update your appsscript.json file with this content:\n\n${manifestContent}\n\nSteps:\n1. Go to Project Settings (gear icon)\n2. Check "Show appsscript.json manifest file"\n3. Replace all content with the above\n4. Save the file`,
    ui.ButtonSet.OK
  );

  console.log("[INFO] Manifest update instructions displayed");
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

// Function to sign out and clear all data
function signOutAndClear() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.alert(
    "Sign Out",
    "Are you sure you want to sign out and clear all data?",
    ui.ButtonSet.YES_NO
  );

  if (result == ui.Button.YES) {
    // Clear all data and authentication
    clearAllData();

    // Show confirmation
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Signed out successfully. Authentication required to access data.",
      "Sign Out Complete"
    );

    // Show authentication dialog
    showOfficeSelectionDialog();
  }
}

// Function to check current office
function checkCurrentOffice() {
  const selectedOffice =
    PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");

  const offices = {
    pd_office: "PD Office (Admin)",
    Adb_hq: "ADB Headquarters (Admin)",
    Office_1: "Office 1 - Birtamod",
    Office_2: "Office 2 - Mechinagar",
    Office_3: "Office 3 - Dhulabari",
    Office_4: "Office 4 - Dhaijan",
    Office_5: "Office 5 - Kankai",
  };

  const ui = SpreadsheetApp.getUi();
  if (selectedOffice) {
    const officeName = offices[selectedOffice] || selectedOffice;
    ui.alert(
      "Current Office",
      `Currently authenticated as: ${officeName}`,
      ui.ButtonSet.OK
    );
  } else {
    ui.alert(
      "No Office Selected",
      "Please select an office from the menu to authenticate.",
      ui.ButtonSet.OK
    );
  }
}

// Function to setup data validation for status column
function setupStatusValidation() {
  console.log("Setting up status validation...");
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Available status options
  const statusOptions = [
    "SUBMITTED",
    "UNDER_EVALUATION",
    "ESCALATED",
    "RESOLVED",
    "DENIED",
    "DISPUTED",
    "CLOSED",
  ];

  // Get the range for status column (Column C) starting from row 2 (data rows)
  const statusRange = sheet.getRange(2, 3, 1000, 1); // Column C, starting row 2, 1000 rows

  // Create data validation rule
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(statusOptions, true)
    .setAllowInvalid(false)
    .setHelpText("Select a valid grievance status")
    .build();

  // Apply the validation rule
  statusRange.setDataValidation(rule);

  // Add note to header cell
  sheet
    .getRange(1, 3)
    .setNote(
      "Click dropdown to select status. Changes will be confirmed with a comment dialog."
    );

  Logger.log("[DEBUG] Status validation setup completed");
  console.log("Status validation setup completed");
}

// Function to protect the sheet and allow only status column editing
function protectSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  try {
    // Remove existing protections first
    const protections = sheet.getProtections(
      SpreadsheetApp.ProtectionType.SHEET
    );
    protections.forEach((protection) => protection.remove());

    // Protect the entire sheet
    const protection = sheet
      .protect()
      .setDescription("Protect grievance data - only status column editable");

    // Get the current user's email
    const userEmail = Session.getActiveUser().getEmail();

    // Add the current user as an editor
    protection.addEditor(userEmail);

    // Create an unprotected range for the status column (Column C)
    const statusColumnRange = sheet.getRange(2, 3, sheet.getMaxRows() - 1, 1); // Column C, starting from row 2
    const unprotectedRange = protection.getUnprotectedRanges();

    // Remove any existing unprotected ranges
    unprotectedRange.forEach((range) =>
      protection.removeUnprotectedRange(range)
    );

    // Add the status column as an unprotected range
    protection.setUnprotectedRanges([statusColumnRange]);

    // Set warning for other edits
    protection.setWarningOnly(true);

    Logger.log("[DEBUG] Sheet protected - only status column (C) is editable");
    console.log("Sheet protected - only status column (C) is editable");
  } catch (error) {
    Logger.log(`[ERROR] Failed to protect sheet: ${error.message}`);
    console.log(`Failed to protect sheet: ${error.message}`);
  }
}

// Function to handle onEdit event (triggered when cells are edited)
function onEdit(e) {
  const startTime = new Date().getTime();

  try {
    const range = e.range;
    const sheet = range.getSheet();
    const row = range.getRow();
    const col = range.getColumn();
    const value = e.value;
    const oldValue = e.oldValue;

    Logger.log(
      `[DEBUG] onEdit triggered - Row: ${row}, Col: ${col}, Value: ${value}, OldValue: ${oldValue}`
    );

    // Only process status column changes (Column C = 3)
    if (col !== 3) {
      Logger.log(`[DEBUG] onEdit - Ignoring non-status column: ${col}`);
      return;
    }

    // Ignore header row
    if (row <= 1) {
      Logger.log(`[DEBUG] onEdit - Ignoring header row: ${row}`);
      return;
    }

    // Check if this is a valid status change
    if (value === oldValue || !value) {
      Logger.log(`[DEBUG] onEdit - No valid status change detected`);
      return;
    }

    Logger.log(
      `[DEBUG] onEdit - Processing status change in row ${row}: "${oldValue}" -> "${value}"`
    );

    // Check authentication status
    const selectedOffice =
      PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");
    Logger.log(`[DEBUG] onEdit - Selected office: ${selectedOffice}`);

    if (!selectedOffice) {
      Logger.log(`[DEBUG] onEdit - No office authenticated, reverting change`);
      range.setValue(oldValue);
      SpreadsheetApp.getUi().alert(
        "Authentication Required",
        "Please authenticate with an office first before updating grievance status.",
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return;
    }

    // Get grievance data from the row
    Logger.log(`[DEBUG] onEdit - Getting grievance data from row ${row}`);
    const grievanceId = sheet.getRange(row, 2).getValue(); // Column B: Grievance ID
    const complainantName = sheet.getRange(row, 5).getValue(); // Column E: Full Name

    Logger.log(
      `[DEBUG] onEdit - Grievance ID: ${grievanceId}, Complainant: ${complainantName}`
    );

    if (!grievanceId) {
      Logger.log(`[DEBUG] onEdit - No valid grievance ID, reverting change`);
      range.setValue(oldValue);
      SpreadsheetApp.getUi().alert(
        "Invalid Row",
        "No valid grievance ID found in this row.",
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return;
    }

    Logger.log(
      `[DEBUG] onEdit - Showing status update dialog for grievance ${grievanceId}`
    );

    // Show confirmation dialog with comment input
    showStatusUpdateDialog(grievanceId, oldValue, value, complainantName, row);

    const endTime = new Date().getTime();
    Logger.log(`[DEBUG] onEdit completed in ${endTime - startTime}ms`);
  } catch (error) {
    const endTime = new Date().getTime();
    Logger.log(
      `[ERROR] onEdit failed after ${endTime - startTime}ms: ${error.message}`
    );

    // Try to revert the change on error
    try {
      const range = e.range;
      const oldValue = e.oldValue;
      range.setValue(oldValue);
      Logger.log(`[DEBUG] onEdit - Reverted change due to error`);
    } catch (revertError) {
      Logger.log(
        `[ERROR] onEdit - Failed to revert change: ${revertError.message}`
      );
    }
  }
}

// Function to show status update dialog
function showStatusUpdateDialog(
  grievanceId,
  oldStatus,
  newStatus,
  complainantName,
  rowNumber
) {
  Logger.log(
    `[DEBUG] showStatusUpdateDialog called - Grievance: ${grievanceId}, Old: ${oldStatus}, New: ${newStatus}, Row: ${rowNumber}`
  );

  const ui = SpreadsheetApp.getUi();

  try {
    // Show confirmation dialog with notes input
    const confirmResponse = ui.prompt(
      "Confirm Status Update",
      `Grievance: ${grievanceId}\nComplainant: ${complainantName}\nStatus Change: "${oldStatus}" → "${newStatus}"\n\nEnter notes (optional):`,
      ui.ButtonSet.OK_CANCEL
    );

    Logger.log(`[DEBUG] User response: ${confirmResponse.getSelectedButton()}`);

    if (confirmResponse.getSelectedButton() === ui.Button.OK) {
      const notes = confirmResponse.getResponseText().trim();
      Logger.log(`[DEBUG] Notes entered: "${notes}"`);

      // Update the status via API (pass oldStatus for potential revert)
      updateGrievanceStatusViaAPI(
        grievanceId,
        newStatus,
        notes,
        rowNumber,
        oldStatus
      );
    } else {
      // User cancelled - revert the status change
      Logger.log(`[DEBUG] User cancelled, reverting status change`);
      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      sheet.getRange(rowNumber, 3).setValue(oldStatus);
      Logger.log(`[DEBUG] Status change cancelled, reverted to ${oldStatus}`);
    }
  } catch (error) {
    console.log(`[WARNING] showStatusUpdateDialog failed: ${error.message}`);
    Logger.log(`[ERROR] showStatusUpdateDialog failed: ${error.message}`);

    // Try to revert the change on error
    try {
      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      sheet.getRange(rowNumber, 3).setValue(oldStatus);
      Logger.log(`[DEBUG] Reverted status change due to error`);
    } catch (revertError) {
      console.log(
        `[WARNING] Failed to revert status change: ${revertError.message}`
      );
    }
  }
}

// Function to update grievance status via API
function updateGrievanceStatusViaAPI(
  grievanceId,
  newStatus,
  notes,
  rowNumber,
  oldStatus
) {
  const startTime = new Date().getTime();
  Logger.log(
    `[DEBUG] updateGrievanceStatusViaAPI called - Grievance: ${grievanceId}, Status: ${newStatus}, Row: ${rowNumber}`
  );

  const ui = SpreadsheetApp.getUi();

  try {
    // Get API configuration
    const apiUrl =
      PropertiesService.getScriptProperties().getProperty("BASE_URL") ||
      "http://localhost:5000";
    const selectedOffice =
      PropertiesService.getScriptProperties().getProperty("SELECTED_OFFICE");

    Logger.log(`[DEBUG] API URL: ${apiUrl}, Office: ${selectedOffice}`);

    // Prepare request data
    const requestData = {
      status_code: newStatus,
      notes: notes || null,
      created_by: selectedOffice,
    };

    Logger.log(`[DEBUG] Request data: ${JSON.stringify(requestData)}`);

    // Make API request to update status
    Logger.log(
      `[DEBUG] Making API request to: ${apiUrl}/api/grievance/${grievanceId}/status`
    );

    const response = UrlFetchApp.fetch(
      `${apiUrl}/api/grievance/${grievanceId}/status`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${selectedOffice}`,
        },
        payload: JSON.stringify(requestData),
      }
    );

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();

    Logger.log(
      `[DEBUG] API Response - Code: ${responseCode}, Text: ${responseText}`
    );

    if (responseCode === 200) {
      // Status already updated in sheet via onEdit, just update the status update date and notes
      Logger.log(`[DEBUG] API call successful, updating sheet columns P and Q`);

      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      const now = new Date();
      sheet.getRange(rowNumber, SHEET_COLUMNS - 1).setValue(now); // Column P: Status Update Date
      sheet.getRange(rowNumber, SHEET_COLUMNS).setValue(notes); // Column Q: Notes

      ui.alert(
        "Status Updated Successfully",
        `Grievance ${grievanceId} status has been updated to "${newStatus}".`,
        ui.ButtonSet.OK
      );

      console.log(
        `[SUCCESS] Status update completed for grievance ${grievanceId}`
      );
      Logger.log(
        `[DEBUG] Successfully updated grievance ${grievanceId} status to ${newStatus}`
      );
    } else {
      // API update failed - revert the status change in the sheet
      Logger.log(`[DEBUG] API call failed, reverting status change`);

      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      sheet.getRange(rowNumber, 3).setValue(oldStatus); // Revert to previous status

      ui.alert(
        "Update Failed",
        `Failed to update status in database. Status change has been reverted.\nResponse: ${responseCode} - ${responseText}`,
        ui.ButtonSet.OK
      );

      console.log(
        `[WARNING] Status update failed for grievance ${grievanceId}`
      );
      Logger.log(
        `[DEBUG] Failed to update grievance ${grievanceId} status, reverted to ${oldStatus}`
      );
    }

    const endTime = new Date().getTime();
    Logger.log(
      `[DEBUG] updateGrievanceStatusViaAPI completed in ${
        endTime - startTime
      }ms`
    );
  } catch (error) {
    const endTime = new Date().getTime();
    console.log(
      `[WARNING] updateGrievanceStatusViaAPI failed after ${
        endTime - startTime
      }ms: ${error.message}`
    );
    Logger.log(`[ERROR] Failed to update grievance status: ${error.message}`);

    // Revert the status change on error
    try {
      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      sheet.getRange(rowNumber, 3).setValue(oldStatus);
      Logger.log(`[DEBUG] Reverted status change due to error`);
    } catch (revertError) {
      console.log(
        `[WARNING] Failed to revert status change: ${revertError.message}`
      );
    }

    ui.alert(
      "Update Failed",
      `Error updating status: ${error.message}\nStatus change has been reverted.`,
      ui.ButtonSet.OK
    );
  }
}
