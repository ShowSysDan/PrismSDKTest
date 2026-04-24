# @prismfm/prism-sdk

nodejs SDK for interacting with the prism.fm API.

We'd love to hear about what you're building with the Prism SDK! If you have questions or want to share your projects, feel free to reach out to us at engineering@prism.fm.

## Installation

### Installing in Your Node.js Project

These instructions assume that you have a project at `~/Projects/my-project`, and
have been tested with nodejs v22:

1. Download the Prism SDK from the download section on this page
2. Place the downloaded zip file in the root of the project: `~/Projects/my-project/prismfm-prism-sdk-x.y.z.tar`. Note: the filename will contain the SDK's version number in place of `x.y.z`
3. Using the terminal, npm install the package:

```bash
# Navigate to your project directory
cd ~/Projects/my-project

# Install the SDK from the downloaded tar file (replace x.y.z with the file name)
npm install --save ./prismfm-prism-sdk-x.y.z.tar
```

## Using the SDK

### Quick Start Example

Once you have the SDK installed, you'll need an API token to authenticate your requests.

**1. Generate an API token**

You can generate an API token in the table at the top of this page. Store this token in a safe place.

**2. Set your token as an environment variable**

```bash
export PRISM_TOKEN="your-token-here"
```

You can verify that your token is set correctly with `env | grep PRISM`. You should see `PRISM_TOKEN="your-token-here"` printed to the console.

**3. Create your first script**

Create a file called `fetch-prism-data.ts` with the following code:

```javascript
import { getPrismSDK } from '@prismfm/prism-sdk';

async function main() {
	const prism = getPrismSDK({});
	const events = await prism.getEvents({
		lastUpdated: '2026-02-09',
	});
	console.log(`fetched ${events.length} events from Prism`);
	const event = await prism.getEventById(1490700);
	console.log(`event: ${event.name}`);
	const venues = await prism.getVenues({ includeInactive: true });
	console.log(`fetched ${venues.length} venues from Prism`);
}

main();
```

**4. Run your script**

```bash
npx tsx fetch-prism-data.ts
```

This example demonstrates the core SDK methods for fetching events, individual event details, and venue data. For more detailed examples, see the Sample Scripts section below.

## Sample Scripts

The SDK includes several sample TypeScript scripts that demonstrate common usage patterns. These scripts are designed to be copied into your project and run with `npx tsx`.

### Getting Started with Sample Scripts

1. **Install the SDK** (if you haven't already):

```bash
npm install --save ./prismfm-prism-sdk-x.y.z.tar
```

2. **Copy sample scripts to your project:**

```bash
cp -r node_modules/@prismfm/prism-sdk/sample-scripts ./
```

This copies all sample scripts into your project directory where you can view, modify, and run them.

3. **Set your API token:**

```bash
export PRISM_TOKEN="your-token-here"
```

4. **Run a sample script with npx tsx:**

```bash
npx tsx sample-scripts/fetch-event-data.ts
```

### Available Sample Scripts

- **`fetch-event-data.ts`** - Demonstrates fetching a single event by ID with progress tracking
- **`fetch-events-data.ts`** - Shows how to fetch multiple events with date range and status filters
- **`fetch-run-of-show-data.ts`** - Example of fetching run of show data for a specific date range
- **`fetch-venues-data.ts`** - Demonstrates fetching venue data including both active and inactive venues

### Sample Script Examples

**Fetch Event by ID:**

```bash
export PRISM_TOKEN="your-token-here"
npx tsx sample-scripts/fetch-event-data.ts
```

**Fetch Multiple Events:**

```bash
npx tsx sample-scripts/fetch-events-data.ts
```

**Fetch Run of Show:**

```bash
npx tsx sample-scripts/fetch-run-of-show-data.ts
```

**Fetch Venues:**

```bash
npx tsx sample-scripts/fetch-venues-data.ts
```

### Modifying Sample Scripts

Once copied to your project, these scripts are yours to modify! They serve as starting points for:

- Initializing the SDK with token authentication
- Using progress tracking callbacks
- Handling different query parameters
- Processing and displaying results

You can customize the date ranges, filters, and output format to match your needs.

## API Token Permissions

API tokens in Prism are scoped to control access to specific resources. When generating a token in Settings > Developer, you can select permission levels that determine which SDK methods you can use.

### Permission Levels

| Permission Level | Description                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| **Read Only**    | Read-only access to events, calendar, venues, run of show, organization settings, and user profile |
| **Read & Write** | Read access plus ability to update calendar holds and upload files to events                       |

#### Read Only

| Token Scope         | Access                                                     |
| ------------------- | ---------------------------------------------------------- |
| `read-events`       | Read events and event files                                |
| `read-calendar`     | Read calendar holds, confirmed dates, and additional dates |
| `read-run-of-show`  | Read run of show data                                      |
| `read-venues`       | Read venue data                                            |
| `read-organization` | Read organization settings                                 |
| `read-user`         | Read current user profile                                  |

#### Read & Write

Includes all Read Only scopes, plus:

| Token Scope      | Access                                                   |
| ---------------- | -------------------------------------------------------- |
| `write-calendar` | Update calendar hold flags (target date, challenge date) |
| `write-events`   | Upload files to events                                   |

The SDK methods below document which permission level is required for each operation.

## API Methods

The SDK provides several methods for interacting with the Prism API:

### Read Only Methods

- `getEventById` - Fetch a single event by its unique ID
- `getEvents` - Fetch a list of events matching query variables
- `getEventFiles` - Fetch files attached to an event
- `getHolds` - Fetch calendar hold dates
- `getCalendarConfirmedAndAdditionalDates` - Fetch confirmed event dates and additional (meta) dates
- `getRunOfShow` - Fetch run of show data for a date range
- `getVenues` - Fetch venue data with optional inactive venues
- `getOrganizationSettings` - Fetch organization settings
- `getCurrentUser` - Fetch current user profile

### Read & Write Methods

- `updateHold` - Update calendar hold flags (target date or challenge date)
- `uploadFile` - Upload a file to an event

### `getEventById`

```typescript
getEventById(id: number, config?: EventFetchConfig): Promise<PrismEventRollup>
```

> **Permission:** Read Only | **Scope:** `read-events`

Fetches a single event by its unique ID.

**Parameters:**

- `id` (number) - The unique identifier of the event to fetch
- `config` (EventFetchConfig, optional) - Configuration object for the request:
    - `timeout?: number` - Request timeout in milliseconds (default: 600000 = 10 minutes)
    - `pollingInterval?: number` - Polling interval in milliseconds (default: 500)
    - `onProgress?: (progress: PrismReportProgress) => void` - Progress callback function

**Returns:** Promise that resolves to a single event object

**Throws:**

- `PrismSDKError` - When the event is not found, API query fails, network errors occur, or batch processing times out

**Example:**

```javascript
const event = await prism.getEventById(1273100);
console.log(event.name, event.venue.name);
```

---

### `getEvents`

```typescript
getEvents(variables: PrismEventRollupQueryVariables, config?: EventFetchConfig): Promise<PrismEventRollup[]>
```

> **Permission:** Read Only | **Scope:** `read-events`

Fetches a list of events matching the provided query variables.

**Parameters:**

- `variables` (object) - Query variables to filter events:
    - `search?: string` - Search for events by name, artist, etc.
    - `startDate?: string` - Start date of the event (YYYY-MM-DD format)
    - `endDate?: string` - End date of the event (YYYY-MM-DD format)
    - `createdAtStart?: string` - Find events created after this date (YYYY-MM-DD format)
    - `createdAtEnd?: string` - Find events created before this date (YYYY-MM-DD format)
    - `eventStatus?: EventStatus[]` - Array of event statuses to include
    - `includeArchivedEvents?: boolean` - Include archived events in results
    - `onlyMad?: boolean` - Only include MAD events
    - `currencies?: string[]` - Filter by specific currencies
    - `lastUpdated?: string` - Find events updated after this date (YYYY-MM-DD format)
    - `companies?: string[]` - Filter by companies associated with event contacts
    - `contacts?: string[]` - Filter by specific contacts on events
    - `genres?: number[]` - Filter by genre IDs
    - `places?: CityState[]` - Filter by city/state combinations where venues are located
    - `artists?: number[]` - Filter by artist IDs
    - `states?: string[]` - Filter by states/regions where venues are located
    - `eventOwners?: number[]` - Filter by event owner user IDs
    - `tags?: number[]` - Filter by event tag IDs
    - `stages?: number[]` - Filter by venue stage IDs
    - `showType?: string` - Filter by show type. Possible values are 'all', 'rental', or 'talent'
- `config` (EventFetchConfig, optional) - Configuration object for the request:
    - `timeout?: number` - Request timeout in milliseconds (default: 600000 = 10 minutes)
    - `pollingInterval?: number` - Polling interval in milliseconds (default: 500)
    - `onProgress?: (progress: PrismReportProgress) => void` - Progress callback function

**Returns:** Promise that resolves to an array of event objects

**Throws:**

- `PrismSDKError` - When GraphQL query fails, network errors occur, batch processing times out, or validation errors are returned by the API

**💡 Tip:** To find valid filter values (artist IDs, genre IDs, tag IDs, etc.), navigate to the Reports page in Prism and apply filters. The URL parameters will show the available filter values you can use with the SDK.

**Example:**

```javascript
import { EventStatus, ShowType } from '@prismfm/prism-sdk';

// Simple usage
const events = await prism.getEvents({
	startDate: '2025-03-01',
	endDate: '2025-04-10',
	eventStatus: [EventStatus.CONFIRMED],
	lastUpdated: '2025-01-01',
	showType: 'all',
});
console.log(`Found ${events.length} events`);

// With progress tracking
const events = await prism.getEvents(
	{
		startDate: '2025-01-01',
		endDate: '2025-12-31',
	},
	{
		onProgress: (progress: PrismReportProgress) => {
			console.debug(progress.toString());
			// Example output:
			// [BATCH-CREATED] Batch def456 created - Starting processing...
			// [POLLING] [██████              ] 30% (5432 events)
			// [BATCH-COMPLETED] Batch processing complete - Loading 5432 events...
			// [PAGE-LOADED] Loading data: Page 1/22
		},
	}
);
```

---

### `getRunOfShow`

```typescript
getRunOfShow(variables: RunOfShowRequest): Promise<RunOfShowItem[]>
```

> **Permission:** Read Only | **Scope:** `read-run-of-show`

**Parameters:**

- `variables` (object) - Query variables to filter run of show data:
    - `startDate: string` - Start date (YYYY-MM-DD format) **[Required]**
    - `endDate: string` - End date (YYYY-MM-DD format) **[Required]**
    - `excludeFrom?: string` - Exclude from date (YYYY-MM-DD format)
    - `excludeUntil?: string` - Exclude until date (YYYY-MM-DD format)
    - `stageIds?: number[]` - Array of stage IDs to filter by
    - `venueIds?: number[]` - Array of venue IDs to filter by
    - `talentAgentIds?: number[]` - Array of talent agent IDs to filter by
    - `eventTagIds?: number[]` - Array of event tag IDs to filter by

**Returns:** Promise that resolves to an array of run of show items with full event, venue, and stage data

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned (non-200 status codes)

**Example:**

```javascript
const runOfShow = await prism.getRunOfShow({
	startDate: '2025-04-10',
	endDate: '2025-04-11',
	stageIds: [123, 456],
	venueIds: [789],
	eventTagIds: [10, 20], // Filter by event tags
});
console.log(`Found ${runOfShow.length} run of show items`);
// Each item includes:
// id: number
// title: string
// occurs_at: string (ISO datetime)
// finishes_at: string (ISO datetime)
// event: { id: number, name: string, confirmed: EventStatus, talent_data?: TalentData[], tags?: EventTag[] }
// event_description: string
// venue: { id: number, name: string, address fields, location data } | null
// stage: { id: number, name: string, color: string } | null
```

---

### `getVenues`

```typescript
getVenues(variables?: VenuesRequest): Promise<Venue[]>
```

> **Permission:** Read Only | **Scope:** `read-venues`

**Parameters:**

- `variables` (object, optional) - Query variables to filter venue data:
    - `includeInactive?: boolean` - Include inactive venues in addition to active ones (default: false - active only)

**Returns:** Promise that resolves to an array of venue objects with full location, stage, and contact data

**Throws:**

- `PrismSDKError` - When GraphQL query fails or network errors occur

**Example:**

```javascript
// Fetch only active venues (default behavior)
const activeVenues = await prism.getVenues();
console.log(`Found ${activeVenues.length} active venues`);

// Fetch all venues including inactive ones
const allVenues = await prism.getVenues({
	includeInactive: true,
});
console.log(`Found ${allVenues.length} total venues`);
// Each venue includes: id, name, location, stages, contacts, timezone, currency, and more
```

---

### `getHolds`

```typescript
getHolds(variables: HoldsRequest): Promise<HoldCalendarEvent[]>
```

> **Permission:** Read Only | **Scope:** `read-calendar`

Fetches calendar hold dates matching the provided filters.

**Parameters:**

- `variables` (object) - Query variables to filter holds:
    - `startDate: string` - Start date (YYYY-MM-DD format) **[Required]**
    - `endDate: string` - End date (YYYY-MM-DD format) **[Required]**
    - `excludeFrom?: string` - Exclude from date (YYYY-MM-DD format)
    - `excludeUntil?: string` - Exclude until date (YYYY-MM-DD format)
    - `stageIds?: number[]` - Array of stage IDs to filter by
    - `venueIds?: number[]` - Array of venue IDs to filter by
    - `talentAgentIds?: number[]` - Array of talent agent IDs to filter by
    - `eventTagIds?: number[]` - Array of event tag IDs to filter by
    - `includeClearedHolds?: boolean` - Include cleared holds (default: false)
    - `includePendingHolds?: boolean` - Include pending holds (default: true)
    - `includeArchivedEvents?: boolean` - Include holds for archived events (default: false)

**Returns:** Promise that resolves to an array of hold calendar events

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned

**Example:**

```javascript
const holds = await prism.getHolds({
	startDate: '2025-04-01',
	endDate: '2025-04-30',
	stageIds: [123],
	includeClearedHolds: true,
});
console.log(`Found ${holds.length} holds`);
// Each hold includes event, stage, venue, and date information
```

---

### `getCalendarConfirmedAndAdditionalDates`

```typescript
getCalendarConfirmedAndAdditionalDates(
	variables: CalendarConfirmedAndAdditionalDatesRequest
): Promise<CalendarConfirmedAndAdditionalDatesResponse>
```

> **Permission:** Read Only | **Scope:** `read-calendar`

Fetches confirmed event dates and additional (meta) dates.

**Parameters:**

- `variables` (object) - Query variables to filter calendar dates:
    - `startDate: string` - Start date (YYYY-MM-DD format) **[Required]**
    - `endDate: string` - End date (YYYY-MM-DD format) **[Required]**
    - `excludeFrom?: string` - Exclude from date (YYYY-MM-DD format)
    - `excludeUntil?: string` - Exclude until date (YYYY-MM-DD format)
    - `stageIds?: number[]` - Array of stage IDs to filter by
    - `venueIds?: number[]` - Array of venue IDs to filter by
    - `talentAgentIds?: number[]` - Array of talent agent IDs to filter by
    - `eventTagIds?: number[]` - Array of event tag IDs to filter by
    - `includePlaceholders?: boolean` - Include placeholder events (default: false)
    - `includeArchivedEvents?: boolean` - Include dates for archived events (default: false)

**Returns:** Promise that resolves to an object with separate `confirmedDates` and `additionalDates` arrays

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned

**Example:**

```javascript
const response = await prism.getCalendarConfirmedAndAdditionalDates({
	startDate: '2025-04-01',
	endDate: '2025-04-30',
	venueIds: [456],
});
console.log(`Found ${response.confirmedDates.length} confirmed dates`);
console.log(`Found ${response.additionalDates.length} additional dates`);
// Confirmed dates are actual event dates
// Additional dates are meta dates (rehearsals, load-in, etc.)
```

---

### `getEventFiles`

```typescript
getEventFiles(eventId: number): Promise<EventFile[]>
```

> **Permission:** Read Only | **Scope:** `read-events`

Fetches files attached to a specific event.

**Parameters:**

- `eventId` (number) - The unique identifier of the event **[Required]**

**Returns:** Promise that resolves to an array of event file objects

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned

**Example:**

```javascript
const files = await prism.getEventFiles(123456);
console.log(`Found ${files.length} files attached to event`);
files.forEach((file) => {
	console.log(`${file.name}: ${file.url}`);
});
```

---

### `getOrganizationSettings`

```typescript
getOrganizationSettings(): Promise<OrganizationSettings>
```

> **Permission:** Read Only | **Scope:** `read-organization`

Fetches organization settings for the authenticated user's organization.

**Parameters:** None

**Returns:** Promise that resolves to the organization settings object

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned

**Example:**

```javascript
const settings = await prism.getOrganizationSettings();
console.log(`Organization: ${settings.name}`);
console.log(`Currency: ${settings.currency}`);
```

---

### `getCurrentUser`

```typescript
getCurrentUser(): Promise<UserProfile>
```

> **Permission:** Read Only | **Scope:** `read-user`

Fetches the current user's profile information.

**Parameters:** None

**Returns:** Promise that resolves to the user profile object including name, email, admin status, and organization data

**Throws:**

- `PrismSDKError` - When API request fails, network errors occur, or HTTP error responses are returned

**Example:**

```javascript
const user = await prism.getCurrentUser();
console.log(`Current user: ${user.name} (${user.email})`);
console.log(`Is admin: ${user.is_admin}`);
console.log(`Organization ID: ${user.organization_id}`);
```

---

### `updateHold`

```typescript
updateHold(holdId: number, data: UpdateHoldRequest): Promise<Hold>
```

> **Permission:** Read & Write | **Scope:** `write-calendar`

Updates a calendar hold's target date or challenge date flag.

**Parameters:**

- `holdId` (number) - The hold ID to update **[Required]**
- `data` (object) - Update data with one of the following (mutually exclusive):
    - `isTargetDate?: boolean | null` - Mark as target date or clear flag
    - `isChallengeDate?: boolean | null` - Mark as challenge date or clear flag

**Returns:** Promise that resolves to the updated Hold object

**Throws:**

- `PrismSDKError` - When API request fails, validation errors occur, or permission is denied

**Example:**

```javascript
// Mark hold as target date
const hold = await prism.updateHold(789, {
	isTargetDate: true,
});

// Clear target date flag
const hold = await prism.updateHold(789, {
	isTargetDate: null,
});

// Mark hold as challenge date
const hold = await prism.updateHold(790, {
	isChallengeDate: true,
});
```

---

### `uploadFile`

```typescript
uploadFile(data: UploadFileRequest): Promise<UploadFileResponse>
```

> **Permission:** Read & Write | **Scope:** `write-events`

Uploads a file to an event.

**Parameters:**

- `data` (object) - Upload request data **[Required]**:
    - `file: File | Blob` - The file to upload **[Required]**
    - `event?: number` - Event ID to attach file to (required unless note_id or talent_agent_id provided)
    - `notes?: string` - Optional notes about the file
    - `tags?: string` - Comma-separated list of tags (e.g. `"contract, rider"`)
    - `visibleAll?: boolean` - Make file visible to all users (default: false)

**Returns:** Promise that resolves to the created file record

**Throws:**

- `PrismSDKError` - When API request fails, validation errors occur, or permission is denied

**Example:**

```javascript
import { readFileSync } from 'fs';

// Upload a file from disk
const fileBuffer = readFileSync('./contract.pdf');
const fileBlob = new Blob([fileBuffer], { type: 'application/pdf' });

const uploadedFile = await prism.uploadFile({
	file: fileBlob,
	event: 123456,
	notes: 'Signed contract',
	tags: 'contract, signed',
	visibleAll: true,
});
console.log(`File uploaded: ${uploadedFile.id}`);
```

---

## Progress Tracking

The `getEventById` and `getEvents` methods support progress tracking through the optional `config` parameter. This is useful for monitoring the progress of large data fetches.

### PrismReportProgress Class

Progress events are reported using the `PrismReportProgress` class, which provides:

- **Event Types**: `batch-created`, `polling`, `batch-completed`, `page-loaded`, `error`
- **Formatted Output**: The `toString()` method provides nicely formatted progress messages
- **Utility Methods**: `isError()` to check for errors

### Progress Event Flow

When fetching events, the following progress events are emitted:

1. **batch-created**: When the batch request is initiated
2. **polling**: Multiple events showing batch processing progress (0-100%)
3. **batch-completed**: When batch processing is complete and page loading begins
4. **page-loaded**: As each page of data is fetched
5. **Function returns**: No "completed" event - the function returns the data

### Example with Progress Tracking

```javascript
import {
	getPrismSDK,
	PrismReportProgress,
	EventStatus,
} from '@prismfm/prism-sdk';

const prism = getPrismSDK({});

const events = await prism.getEvents(
	{
		startDate: '2025-01-01',
		endDate: '2025-12-31',
		eventStatus: [EventStatus.CONFIRMED],
	},
	{
		timeout: 900000, // 15 minutes
		onProgress: (progress: PrismReportProgress) => {
			// Use console.debug to keep stdout clean for data output
			if (progress.isError()) {
				console.error(progress.toString());
				// Example error output:
				// [ERROR] ✗ Error: Network timeout after 15 minutes
			} else {
				console.debug(progress.toString());
				// Example output:
				// [BATCH-CREATED] Batch ghi789 created - Starting processing...
				// [POLLING] [██████████          ] 50% (12000 events)
				// [BATCH-COMPLETED] Batch processing complete - Loading 12000 events...
				// [PAGE-LOADED] Loading data: Page 1/48

				// Process incremental data as it loads
				if (progress.type === 'page-loaded' && progress.data) {
					const eventNames = progress.data.map(
						(event: PrismEventRollup) => event.name
					);
					console.log(
						`Page ${progress.page} loaded with ${progress.data.length} events:`,
						eventNames
					);
				}
			}
		},
	}
);

// Output data to stdout (clean for piping to jq)
console.log(JSON.stringify(events, null, 2));
```

### Configuration Options

The `EventFetchConfig` object supports:

- **timeout**: Total timeout in milliseconds (default: 600000 = 10 minutes)
- **pollingInterval**: How often to check batch status in milliseconds (default: 500)
- **onProgress**: Callback function that receives `PrismReportProgress` events

### Progress Tracking Types

```typescript
// Progress event types
type ProgressEventType = 'batch-created' | 'polling' | 'batch-completed' | 'page-loaded' | 'error';

// Progress report class
class PrismReportProgress {
	type: ProgressEventType;
	timestamp: Date;
	batchId?: string;
	progress?: number; // 0-100
	total?: number;
	page?: number;
	totalPages?: number;
	error?: Error;
	data?: PrismEventRollup[]; // Incremental data from loaded page

	toString(): string; // Formatted output
	isError(): boolean; // Utility method
}

// Event fetch configuration
interface EventFetchConfig {
	timeout?: number;
	pollingInterval?: number;
	onProgress?: (progress: PrismReportProgress) => void;
}
```

## Error Handling

The SDK throws `PrismSDKError` for all error scenarios including API failures, network issues, validation problems, configuration errors, and resource not found errors.

### PrismSDKError

`PrismSDKError` is the single error type you'll encounter when working with the SDK.

**Properties:**

- **`message`** (string) - Human-readable error message describing what went wrong
- **`name`** (string) - Always set to `'PrismSDKError'`
- **`validationErrors`** (Record<string, string[]> | undefined) - Field-level validation errors from the API (when applicable)

**When it's thrown:**

- API query errors
- Network failures
- Server-side validation failures
- Configuration errors (missing token, invalid parameters)
- Resource not found (event not found by ID)
- HTTP error responses (non-200 status codes)

### Error Handling Best Practices

Always wrap SDK method calls in try-catch blocks to handle potential errors:

```typescript
import { getPrismSDK, PrismSDKError } from '@prismfm/prism-sdk';

const prism = getPrismSDK({});

try {
	const events = await prism.getEvents({
		startDate: '2025-01-01',
		endDate: '2025-12-31',
	});
	console.log(`Successfully fetched ${events.length} events`);
} catch (error) {
	if (error instanceof PrismSDKError) {
		console.error('Error:', error.message);

		// Check for validation errors if applicable
		if (error.validationErrors) {
			console.error('Validation errors:', error.validationErrors);
			// Example: { startDate: ['Date must be in YYYY-MM-DD format'] }
		}
	} else {
		console.error('Unexpected error:', error);
	}
}
```

### Validation Errors

When the API returns validation errors, they're available in the `validationErrors` property as a Record mapping field names to arrays of error messages:

```typescript
try {
	const events = await prism.getEvents({
		startDate: 'invalid-date',
		endDate: '2025-12-31',
	});
} catch (error) {
	if (error instanceof PrismSDKError && error.validationErrors) {
		for (const [field, messages] of Object.entries(error.validationErrors)) {
			console.error(`${field}: ${messages.join(', ')}`);
		}
		// Output: startDate: Date must be in YYYY-MM-DD format
	}
}
```

## TypeScript Type Definitions

The SDK is written in TypeScript and provides comprehensive type definitions for all data structures. When using the SDK, you have access to the following key types:

### Core Types

```typescript
import {
	// Main SDK interface
	PrismSDK,

	// Event data types
	PrismEventRollup,
	EventStatus,
	EventFile,

	// Run of show types
	RunOfShowItem,

	// Venue types
	Venue,
	Stage,

	// Calendar types
	HoldCalendarEvent,
	ConfirmedCalendarEvent,
	Hold,
	HoldsRequest,
	CalendarConfirmedAndAdditionalDatesRequest,
	CalendarConfirmedAndAdditionalDatesResponse,
	UpdateHoldRequest,

	// Organization & User types
	OrganizationSettings,
	UserProfile,

	// Platform ticket types
	PlatformTicketInput,
	PlatformTicketUpdate,
	ConnectPlatformEventRequest,

	// File upload types
	UploadFileRequest,
	UploadFileResponse,

	// Progress tracking types
	PrismReportProgress,
	ProgressEventType,
	EventFetchConfig,

	// Error types
	PrismSDKError,

	// SDK initialization
	PrismSDKOptions,
	getPrismSDK,
} from '@prismfm/prism-sdk';
```

### Event Status Enum

The `EventStatus` enum provides all possible event statuses:

```typescript
enum EventStatus {
	HOLD = 0,
	CONFIRMED = 2,
	IN_SETTLEMENT = 3,
	SETTLED = 4,
}
```

### PrismEventRollup Type

The `PrismEventRollup` type is the main interface for event objects returned by the SDK.

```typescript
// Example usage with full type safety
const event: PrismEventRollup = await prism.getEventById(123456);
console.log(event.name); // TypeScript knows this is a string
```

### Venue Types

```typescript
interface Venue {
	id: number;
	name: string;
	customer_id: string;
	organization_id: number;
	active: boolean | number;
	currency: string;
	can_request_to_host_venue: boolean;
	created_at: string | null;
	updated_at: string | null;
	convert_to_usd: boolean;
	capacity: number | null;
	default_template_id: string | null;
	default_logo_id: number | null;
	eb_venue_id: number | null;
	facility_fee: number;
	external_only_facility_fee: boolean;
	tax_rate: number;
	tax_type: string;
	timezone: string;
	show_best_available: boolean;
	central_venue_id: number | null;
	contact_ids: number[];
	default_hold_level: number | null;
	auto_promote_holds: boolean | null;
	address_1_short: string;
	address_1_long: string;
	address_2_short: string;
	address_2_long: string;
	city_short: string;
	city_long: string;
	state_short: string;
	state_long: string;
	country_short: string;
	country_long: string;
	zip: string;
	google_place_id: string;
	location_migration_failure: boolean;
	location: string;
	stages: Stage[];
}

interface Stage {
	id: number;
	name: string;
	active: boolean;
	capacity: number;
	color: string;
	venue_id: number;
}

interface RunOfShowItem {
	id: number;
	title: string;
	occurs_at: string;
	finishes_at: string;
	event: EventData;
	venue: VenueData | null;
	stage: StageData | null;
}
```

### JavaScript Usage

While the SDK is written in TypeScript, it can be used in regular JavaScript projects. The type definitions are included for TypeScript users but don't affect JavaScript usage.

## Development

This package is part of the Prism monorepo and uses **Turborepo + Prism CLI** for build and publishing.

### Building the Package

```bash
# From repository root - builds this package and its dependencies
npx turbo build --filter="./prism-public-sdk-package"

# Build public version (uses project-specific turbo.json config)
npx turbo build:public --filter="./prism-public-sdk-package"

# Build both internal and public versions
npx turbo build build:public --filter="./prism-public-sdk-package"
```

**Note:** This package has its own `turbo.json` config file for public build tasks (`build:public`, `prebuild:public`, etc.) while inheriting common tasks from the root configuration.

### Testing

```bash
# Run tests from repository root
npx turbo test --filter="./prism-public-sdk-package"

# Run tests with coverage
npx turbo test:coverage --filter="./prism-public-sdk-package"

# Test the build output
npx turbo test:build --filter="./prism-public-sdk-package"
```

### Publishing

The package uses **Turborepo + Prism CLI** for automated publishing to multiple targets:

```bash
# Publish using Prism CLI (handles both S3 and GitHub Packages)
npx turbo publish --filter="./prism-public-sdk-package"

# Or use the npm script directly
npm run publish
```

**Publishing targets** (configured in `package.json` prism config):

- **public-sdk**: S3 bucket distribution for public download
- **internal-sdk**: GitHub Packages for internal npm installation

Automated publishing happens via GitHub Actions using matrix-based deployment with the `discover-child-projects` action.
