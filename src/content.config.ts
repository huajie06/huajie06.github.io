import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders'; // If you are using the glob loader in Astro 5

const blog = defineCollection({
    // In Astro 5, you often use a loader. 
    // If your previous config worked with 'type: content', keep it.
    // But if you see an error about loaders, use this:
    // loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),

    type: 'content', // Keep this if you aren't using loaders yet
    schema: z.object({
        title: z.string(),
        description: z.string(),
        pubDate: z.coerce.date(),
        updatedDate: z.coerce.date().optional(),
        heroImage: z.string().optional(),
        tags: z.array(z.string()).optional(), // <--- Your missing piece
    }),
});

export const collections = { blog };