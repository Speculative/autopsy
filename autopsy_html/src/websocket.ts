import type { AutopsyData, CallSite, StackTrace, DashboardData, DashboardCallSite, CountEntry, HistogramEntry, TimelineEntry, HappenedEntry } from './types';

export interface WebSocketConfig {
  url: string;
  onSnapshot: (data: AutopsyData) => void;
  onUpdate: (update: IncrementalUpdate) => void;
  onError: (error: Event) => void;
  onClose: () => void;
}

export interface IncrementalUpdate {
  type: 'log' | 'count' | 'hist' | 'timeline' | 'happened' | 'snapshot';
  call_site?: {
    filename: string;
    line: number;
    function_name: string;
    class_name?: string;
  };
  value_group?: any;
  stack_trace?: Record<string, StackTrace>;
  data?: AutopsyData;
}

export function createWebSocketConnection(config: WebSocketConfig): WebSocket {
  const ws = new WebSocket(config.url);

  ws.onopen = () => {
    console.log('WebSocket connected');
  };

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data) as IncrementalUpdate;

    if (message.type === 'snapshot' && message.data) {
      config.onSnapshot(message.data);
    } else {
      config.onUpdate(message);
    }
  };

  ws.onerror = config.onError;
  ws.onclose = config.onClose;

  return ws;
}

export function mergeIncrementalUpdate(
  current: AutopsyData,
  update: IncrementalUpdate
): AutopsyData {
  const updated = { ...current };

  if (update.type === 'log' && update.call_site && update.value_group) {
    updated.call_sites = mergeLogUpdate(
      current.call_sites,
      update.call_site,
      update.value_group
    );
  } else if ((update.type === 'count' || update.type === 'hist' ||
              update.type === 'timeline' || update.type === 'happened') &&
             update.call_site && update.value_group) {
    // Dashboard updates need to update BOTH call_sites (for Streams/History)
    // AND dashboard data (for Dashboard view)
    updated.call_sites = mergeDashboardUpdate(
      current.call_sites,
      update.call_site,
      update.value_group
    );

    // Also update the dashboard data structure for reactive Dashboard view
    updated.dashboard = mergeDashboardData(
      current.dashboard,
      update.type as 'count' | 'hist' | 'timeline' | 'happened',
      update.call_site,
      update.value_group
    );
  }

  if (update.stack_trace) {
    updated.stack_traces = {
      ...current.stack_traces,
      ...update.stack_trace
    };
  }

  return updated;
}

function mergeLogUpdate(
  existing: CallSite[],
  newCallSite: any,
  valueGroup: any
): CallSite[] {
  const key = `${newCallSite.filename}:${newCallSite.line}`;
  const existingIndex = existing.findIndex(
    cs => `${cs.filename}:${cs.line}` === key
  );

  if (existingIndex >= 0) {
    const updated = [...existing];
    updated[existingIndex] = {
      ...updated[existingIndex],
      value_groups: [...updated[existingIndex].value_groups, valueGroup]
    };
    return updated;
  } else {
    return [...existing, {
      filename: newCallSite.filename,
      line: newCallSite.line,
      function_name: newCallSite.function_name,
      class_name: newCallSite.class_name,
      value_groups: [valueGroup]
    }];
  }
}

function mergeDashboardUpdate(
  existing: CallSite[],
  newCallSite: any,
  valueGroup: any
): CallSite[] {
  const key = `${newCallSite.filename}:${newCallSite.line}`;
  const existingIndex = existing.findIndex(
    cs => `${cs.filename}:${cs.line}` === key
  );

  if (existingIndex >= 0) {
    // Call site exists, append the value_group
    const updated = [...existing];
    updated[existingIndex] = {
      ...updated[existingIndex],
      value_groups: [...updated[existingIndex].value_groups, valueGroup]
    };
    return updated;
  } else {
    // New call site for dashboard data
    return [...existing, {
      filename: newCallSite.filename,
      line: newCallSite.line,
      function_name: newCallSite.function_name,
      class_name: newCallSite.class_name,
      value_groups: [valueGroup],
      is_dashboard: true
    }];
  }
}

function mergeDashboardData(
  current: DashboardData | undefined,
  type: 'count' | 'hist' | 'timeline' | 'happened',
  callSite: any,
  valueGroup: any
): DashboardData {
  // Initialize dashboard if it doesn't exist
  const dashboard: DashboardData = current || {
    counts: [],
    histograms: [],
    timeline: [],
    happened: []
  };

  const dashboardCallSite: DashboardCallSite = {
    filename: callSite.filename,
    line: callSite.line,
    function_name: callSite.function_name,
    class_name: callSite.class_name
  };

  if (type === 'count') {
    return mergeCountData(dashboard, dashboardCallSite, valueGroup);
  } else if (type === 'hist') {
    return mergeHistData(dashboard, dashboardCallSite, valueGroup);
  } else if (type === 'timeline') {
    return mergeTimelineData(dashboard, dashboardCallSite, valueGroup);
  } else if (type === 'happened') {
    return mergeHappenedData(dashboard, dashboardCallSite, valueGroup);
  }

  return dashboard;
}

function mergeCountData(
  dashboard: DashboardData,
  callSite: DashboardCallSite,
  valueGroup: any
): DashboardData {
  const counts = [...dashboard.counts];
  const key = `${callSite.filename}:${callSite.line}`;
  const existingIndex = counts.findIndex(
    entry => `${entry.call_site.filename}:${entry.call_site.line}` === key
  );

  const valueKey = JSON.stringify(valueGroup.value);

  if (existingIndex >= 0) {
    // Update existing count entry
    const updated = [...counts];
    const entry = { ...updated[existingIndex] };
    const valueCounts = { ...entry.value_counts };

    if (valueCounts[valueKey]) {
      valueCounts[valueKey] = {
        count: valueCounts[valueKey].count + 1,
        stack_trace_ids: [
          ...valueCounts[valueKey].stack_trace_ids,
          ...(valueGroup.stack_trace_id ? [valueGroup.stack_trace_id] : [])
        ],
        log_indices: [...valueCounts[valueKey].log_indices, valueGroup.log_index]
      };
    } else {
      valueCounts[valueKey] = {
        count: 1,
        stack_trace_ids: valueGroup.stack_trace_id ? [valueGroup.stack_trace_id] : [],
        log_indices: [valueGroup.log_index]
      };
    }

    entry.value_counts = valueCounts;
    updated[existingIndex] = entry;
    return { ...dashboard, counts: updated };
  } else {
    // New count entry
    const newEntry: CountEntry = {
      call_site: callSite,
      value_counts: {
        [valueKey]: {
          count: 1,
          stack_trace_ids: valueGroup.stack_trace_id ? [valueGroup.stack_trace_id] : [],
          log_indices: [valueGroup.log_index]
        }
      }
    };
    return { ...dashboard, counts: [...counts, newEntry] };
  }
}

function mergeHistData(
  dashboard: DashboardData,
  callSite: DashboardCallSite,
  valueGroup: any
): DashboardData {
  const histograms = [...dashboard.histograms];
  const key = `${callSite.filename}:${callSite.line}`;
  const existingIndex = histograms.findIndex(
    entry => `${entry.call_site.filename}:${entry.call_site.line}` === key
  );

  const histValue: HistogramEntry['values'][0] = {
    value: valueGroup.value,
    stack_trace_id: valueGroup.stack_trace_id,
    log_index: valueGroup.log_index
  };

  if (existingIndex >= 0) {
    const updated = [...histograms];
    updated[existingIndex] = {
      ...updated[existingIndex],
      values: [...updated[existingIndex].values, histValue]
    };
    return { ...dashboard, histograms: updated };
  } else {
    const newEntry: HistogramEntry = {
      call_site: callSite,
      values: [histValue]
    };
    return { ...dashboard, histograms: [...histograms, newEntry] };
  }
}

function mergeTimelineData(
  dashboard: DashboardData,
  callSite: DashboardCallSite,
  valueGroup: any
): DashboardData {
  const newEntry: TimelineEntry = {
    timestamp: valueGroup.timestamp,
    event_name: valueGroup.event_name,
    call_site: callSite,
    stack_trace_id: valueGroup.stack_trace_id,
    log_index: valueGroup.log_index
  };

  return {
    ...dashboard,
    timeline: [...dashboard.timeline, newEntry]
  };
}

function mergeHappenedData(
  dashboard: DashboardData,
  callSite: DashboardCallSite,
  valueGroup: any
): DashboardData {
  const happened = [...dashboard.happened];
  const key = `${callSite.filename}:${callSite.line}`;
  const existingIndex = happened.findIndex(
    entry => `${entry.call_site.filename}:${entry.call_site.line}` === key
  );

  if (existingIndex >= 0) {
    const updated = [...happened];
    updated[existingIndex] = {
      ...updated[existingIndex],
      count: updated[existingIndex].count + 1,
      stack_trace_ids: [
        ...updated[existingIndex].stack_trace_ids,
        ...(valueGroup.stack_trace_id ? [valueGroup.stack_trace_id] : [])
      ],
      log_indices: [...updated[existingIndex].log_indices, valueGroup.log_index]
    };
    return { ...dashboard, happened: updated };
  } else {
    const newEntry: HappenedEntry = {
      call_site: callSite,
      count: 1,
      stack_trace_ids: valueGroup.stack_trace_id ? [valueGroup.stack_trace_id] : [],
      log_indices: [valueGroup.log_index],
      message: valueGroup.message
    };
    return { ...dashboard, happened: [...happened, newEntry] };
  }
}
