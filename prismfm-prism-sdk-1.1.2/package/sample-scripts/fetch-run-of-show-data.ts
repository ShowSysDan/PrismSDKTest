import { getPrismSDK, PrismSDK, RunOfShowItem } from '@prismfm/prism-sdk';

async function main(): Promise<void> {
	const prismSDK: PrismSDK = getPrismSDK({
		// accessToken: process.env.PRISM_TOKEN,
	});

	const runOfShow: RunOfShowItem[] = await prismSDK.getRunOfShow({
		startDate: '2025-04-10',
		endDate: '2025-04-11',
	});
	// eslint-disable-next-line no-console
	console.log(JSON.stringify(runOfShow, null, 2));
}

main();
