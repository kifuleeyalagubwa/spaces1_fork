package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sync"

	"github.com/pion/webrtc/v3"
)

// Room structure to manage broadcasters and consumers
type Room struct {
	Broadcaster *webrtc.PeerConnection
	Consumers   map[string]*webrtc.PeerConnection // Key: Consumer ID
	Tracks      []*webrtc.TrackRemote
	lock        sync.RWMutex
}

var (
	rooms         = make(map[string]*Room)
	roomsMu       sync.RWMutex
	settingEngine = webrtc.SettingEngine{}
)

func init() {
	// Termux-specific settings
	settingEngine.SetIncludeLoopbackCandidate(true)
	settingEngine.SetNAT1To1IPs([]string{"127.0.0.1"}, webrtc.ICECandidateTypeHost)
	
	// Use only loopback networking
	settingEngine.SetNetworkTypes([]webrtc.NetworkType{webrtc.NetworkTypeLoopback})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/broadcast", broadcastHandler) // Teacher endpoint
	http.HandleFunc("/consume", consumeHandler)     // Student endpoint
	http.HandleFunc("/health", healthHandler)

	log.Printf("✅ SFU Server running on :%s\n", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func broadcastHandler(w http.ResponseWriter, r *http.Request) {
	enableCors(&w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req struct {
		RoomID string                     `json:"room_id"`
		Offer  webrtc.SessionDescription `json:"offer"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	// Create API with pre-configured setting engine
	api := webrtc.NewAPI(webrtc.WithSettingEngine(settingEngine))

	// Use minimal configuration with loopback policy
	peerConnection, err := api.NewPeerConnection(webrtc.Configuration{
		ICEServers: []webrtc.ICEServer{
			{URLs: []string{"stun:stun.l.google.com:19302"}},
		},
		ICETransportPolicy: webrtc.ICETransportPolicyLoopback,
	})
	if err != nil {
		log.Println("❌ Failed to create broadcaster PC:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Create or get room
	roomsMu.Lock()
	room, exists := rooms[req.RoomID]
	if !exists {
		room = &Room{
			Consumers: make(map[string]*webrtc.PeerConnection),
		}
		rooms[req.RoomID] = room
		log.Printf("🚀 Room created: %s", req.RoomID)
	}
	roomsMu.Unlock()

	room.lock.Lock()
	room.Broadcaster = peerConnection
	room.lock.Unlock()

	// Handle incoming tracks
	peerConnection.OnTrack(func(track *webrtc.TrackRemote, receiver *webrtc.RTPReceiver) {
		log.Printf("🎥 Received track in room %s: %s", req.RoomID, track.Kind().String())
		
		room.lock.Lock()
		room.Tracks = append(room.Tracks, track)
		room.lock.Unlock()
		
		// Forward track to existing consumers using relay
		room.lock.RLock()
		for id, consumer := range room.Consumers {
			go relayTrackToConsumer(track, consumer, id)
		}
		room.lock.RUnlock()
	})

	peerConnection.OnICEConnectionStateChange(func(state webrtc.ICEConnectionState) {
		log.Printf("📡 ICE state (Broadcaster): %s", state.String())
		if state == webrtc.ICEConnectionStateDisconnected ||
			state == webrtc.ICEConnectionStateFailed {
			cleanupRoom(req.RoomID)
		}
	})

	// Handle ICE candidates
	peerConnection.OnICECandidate(func(c *webrtc.ICECandidate) {
		if c == nil {
			return
		}
		log.Printf("🧊 ICE Candidate (Broadcaster): %s", c.String())
	})

	if err = peerConnection.SetRemoteDescription(req.Offer); err != nil {
		log.Println("❌ SetRemoteDescription failed:", err)
		http.Error(w, "Invalid offer", http.StatusBadRequest)
		return
	}

	answer, err := peerConnection.CreateAnswer(nil)
	if err != nil {
		log.Println("❌ Failed to create answer:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Create gathering complete promise
	gatherComplete := webrtc.GatheringCompletePromise(peerConnection)

	if err = peerConnection.SetLocalDescription(answer); err != nil {
		log.Println("❌ Failed to set local description:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Wait for ICE gathering to complete
	<-gatherComplete

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(*peerConnection.LocalDescription())
	log.Println("✅ Broadcaster answer sent")
}

// Relay track to a specific consumer by copying packets
func relayTrackToConsumer(remoteTrack *webrtc.TrackRemote, consumer *webrtc.PeerConnection, consumerID string) {
	// Create a local track that we'll send to the consumer
	localTrack, err := webrtc.NewTrackLocalStaticRTP(
		remoteTrack.Codec().RTPCodecCapability,
		remoteTrack.ID(),
		remoteTrack.StreamID(),
	)
	if err != nil {
		log.Printf("❌ Failed to create local track for consumer %s: %v", consumerID, err)
		return
	}

	// Add track to consumer
	if _, err := consumer.AddTrack(localTrack); err != nil {
		log.Printf("❌ Failed to add track to consumer %s: %v", consumerID, err)
		return
	}

	// Start copying packets from broadcaster to consumer
	buf := make([]byte, 1500)
	for {
		n, _, err := remoteTrack.Read(buf)
		if err != nil {
			log.Printf("❌ Track read error for consumer %s: %v", consumerID, err)
			return
		}

		// Write to consumer
		if _, err := localTrack.Write(buf[:n]); err != nil {
			log.Printf("❌ Track write error for consumer %s: %v", consumerID, err)
			return
		}
	}
}

func consumeHandler(w http.ResponseWriter, r *http.Request) {
	enableCors(&w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req struct {
		RoomID string                     `json:"room_id"`
		UserID string                     `json:"user_id"`
		Offer  webrtc.SessionDescription `json:"offer"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	roomsMu.RLock()
	room, exists := rooms[req.RoomID]
	roomsMu.RUnlock()

	if !exists || room.Broadcaster == nil {
		http.Error(w, "Room not found or no broadcaster", http.StatusNotFound)
		return
	}

	// Create API with pre-configured setting engine
	api := webrtc.NewAPI(webrtc.WithSettingEngine(settingEngine))

	peerConnection, err := api.NewPeerConnection(webrtc.Configuration{
		ICEServers: []webrtc.ICEServer{
			{URLs: []string{"stun:stun.l.google.com:19302"}},
		},
		ICETransportPolicy: webrtc.ICETransportPolicyLoopback,
	})
	if err != nil {
		log.Println("❌ Failed to create consumer PC:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Store consumer
	room.lock.Lock()
	room.Consumers[req.UserID] = peerConnection
	room.lock.Unlock()

	// Start relaying existing tracks to this new consumer
	room.lock.RLock()
	for _, track := range room.Tracks {
		go relayTrackToConsumer(track, peerConnection, req.UserID)
	}
	room.lock.RUnlock()

	peerConnection.OnICEConnectionStateChange(func(state webrtc.ICEConnectionState) {
		log.Printf("📡 ICE state (Consumer): %s", state.String())
		if state == webrtc.ICEConnectionStateDisconnected ||
			state == webrtc.ICEConnectionStateFailed {
			room.lock.Lock()
			delete(room.Consumers, req.UserID)
			room.lock.Unlock()
			peerConnection.Close()
		}
	})

	// Handle ICE candidates
	peerConnection.OnICECandidate(func(c *webrtc.ICECandidate) {
		if c == nil {
			return
		}
		log.Printf("🧊 ICE Candidate (Consumer): %s", c.String())
	})

	if err = peerConnection.SetRemoteDescription(req.Offer); err != nil {
		log.Println("❌ SetRemoteDescription failed:", err)
		http.Error(w, "Invalid offer", http.StatusBadRequest)
		return
	}

	answer, err := peerConnection.CreateAnswer(nil)
	if err != nil {
		log.Println("❌ Failed to create answer:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Create gathering complete promise
	gatherComplete := webrtc.GatheringCompletePromise(peerConnection)

	if err = peerConnection.SetLocalDescription(answer); err != nil {
		log.Println("❌ Failed to set local description:", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Wait for ICE gathering to complete
	<-gatherComplete

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(*peerConnection.LocalDescription())
	log.Println("✅ Consumer answer sent")
}

func enableCors(w *http.ResponseWriter) {
	(*w).Header().Set("Access-Control-Allow-Origin", "*")
	(*w).Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	(*w).Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func cleanupRoom(roomID string) {
	roomsMu.Lock()
	defer roomsMu.Unlock()
	
	if room, exists := rooms[roomID]; exists {
		if room.Broadcaster != nil {
			room.Broadcaster.Close()
		}
		for id, consumer := range room.Consumers {
			consumer.Close()
			delete(room.Consumers, id)
		}
		delete(rooms, roomID)
		log.Printf("🧹 Cleaned up room: %s", roomID)
	}
}