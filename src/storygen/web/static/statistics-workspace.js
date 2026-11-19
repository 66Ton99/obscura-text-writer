import {state} from './editor.js';
import {api} from './api.js';
import {isStoreEdition} from './app-info.js';
import {installSceneStatistics} from './scene-statistics.js';
installSceneStatistics({state,api,document,store:await isStoreEdition()});
