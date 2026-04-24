/* eslint-disable no-console */
import { PrismSDK, Venue, getPrismSDK } from '@prismfm/prism-sdk';

async function main(): Promise<void> {
	const prismSDK: PrismSDK = getPrismSDK({
		// accessToken: process.env.PRISM_TOKEN,
	});

	// Fetch only active venues (default behavior)
	console.log('=== Active Venues Only (Default) ===');
	const activeVenues: Venue[] = await prismSDK.getVenues();
	console.log(`Found ${activeVenues.length} active venues`);
	console.log(JSON.stringify(activeVenues, null, 2));

	// Fetch all venues including inactive ones
	console.log('\n=== All Venues (Including Inactive) ===');
	const allVenues: Venue[] = await prismSDK.getVenues({
		includeInactive: true,
	});
	console.log(`Found ${allVenues.length} total venues`);
	console.log(JSON.stringify(allVenues, null, 2));
}

main().catch((error: Error): void => {
	console.error('Error fetching venues:', error);
	process.exit(1);
});
