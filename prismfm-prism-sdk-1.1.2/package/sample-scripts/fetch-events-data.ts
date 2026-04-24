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

	const events: PrismEventRollup[] = await prismSDK.getEvents(
		{
			startDate: '2025-01-01',
			endDate: '2025-06-10',
			eventStatus: [EventStatus.CONFIRMED],
		},
		{
			// Optional: Add progress tracking
			onProgress: (progress: PrismReportProgress): void => {
				console.error(progress.toString());
			},
			// Optional: Custom timeout (default is 10 minutes)
			// timeout: 900000, // 15 minutes
		}
	);
	// Only output the actual data to stdout for piping to jq
	// eslint-disable-next-line no-console
	console.log(JSON.stringify(events, null, 2));
}

main();
