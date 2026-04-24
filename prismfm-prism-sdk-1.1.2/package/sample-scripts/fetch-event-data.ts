import {
	EventStatus,
	PrismEventRollup,
	PrismReportProgress,
	PrismSDK,
	getPrismSDK,
} from '@prismfm/prism-sdk';

async function main(): Promise<void> {
	const prismSDK: PrismSDK = getPrismSDK({
		// accessToken: process.env.PRISM_TOKEN,
	});

	// First get a list of events
	const events: PrismEventRollup[] = await prismSDK.getEvents({
		startDate: '2025-03-01',
		endDate: '2025-04-10',
		eventStatus: [EventStatus.CONFIRMED],
	});

	// Then fetch a single event by ID with progress tracking
	const event: PrismEventRollup = await prismSDK.getEventById(events[0].id, {
		onProgress: (progress: PrismReportProgress): void => {
			console.error(progress.toString());
		},
	});

	// Only output the actual data to stdout for piping to jq
	// eslint-disable-next-line no-console
	console.log(JSON.stringify(event, null, 2));
}

main();
