import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
	type: 'content',
	// Schema validation logic
	schema: z.object({
		title: z.string(),
		description: z.string(),
		// Transform string to Date object
		pubDate: z.coerce.date(),
		updatedDate: z.coerce.date().optional(),
		heroImage: z.string().optional(),
        
        // THIS IS THE KEY PART MISSING:
		tags: z.array(z.string()).optional(),
	}),
});

export const collections = { blog };