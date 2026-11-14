import { defineConfig } from 'vite';
import { resolve } from 'path';
const page = (n) => resolve(__dirname, n + '.html');
export default defineConfig({
  build: { rollupOptions: { input: { index: page('index'), nisar: page('nisar'), insights: page('insights'), map: page('map'), about: page('about'), collaborators: page('collaborators') } } },
});
