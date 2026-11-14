import {JobStatus} from '../../constants/enums.js';
import {esc} from '../../utils/dom.js';
export const status=v=>'<span class="status '+esc(v)+'">'+esc(JobStatus[v]||v)+'</span>';
export const invalidBadge=j=>j.invalid?'<span class="status invalid" title="'+esc(j.invalid_reason||'')+'">已失效</span>':'';
